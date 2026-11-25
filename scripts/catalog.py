"""Validate and render the maintainer-reviewed AISciHub OSS registry.

Only fixed, public GitHub REST endpoints are read. The registry—not GitHub
issues, repository descriptions, or API results—decides catalog membership.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry

if __package__:
    from .gallery import render_gallery
else:
    from gallery import render_gallery


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.github.com"
REPO_PATTERN = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}"
)
CATEGORIES = {
    "ai-and-automation": "AI & automation",
    "apps-and-utilities": "Apps & utilities",
    "civic-tech": "Civic tech & accessibility",
    "developer-tools": "Developer tools & security",
    "scientific-computing": "Scientific computing & data",
    "web-and-browser": "Web & browser",
}
MAX_LOCAL_BYTES = 512 * 1024
MAX_API_BYTES = 4 * 1024 * 1024
MAX_COVER_BYTES = 4 * 1024 * 1024
COVER_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\.(png|jpg|webp)")


class CatalogError(Exception):
    """An invalid registry, unavailable public resource, or invalid snapshot."""


class RegistryLoader(yaml.SafeLoader):
    """Use YAML as data; disallow aliases, anchors, and duplicate keys."""

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None):
            raise CatalogError("YAML anchors and aliases are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise CatalogError("Expected a YAML mapping")
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise CatalogError("YAML mapping keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_bounded(path, limit=MAX_LOCAL_BYTES):
    if path.is_symlink():
        raise CatalogError(f"{path.name} must not be a symbolic link")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise CatalogError(f"{path.name} exceeds the size limit")
    return data


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("JSON contains duplicate keys")
        result[key] = value
    return result


def reject_json_constant(_value):
    raise CatalogError("JSON contains a non-finite number")


def decode_json(data):
    try:
        return json.loads(
            data,
            object_pairs_hook=unique_json_object,
            parse_constant=reject_json_constant,
        )
    except (ValueError, RecursionError) as exc:
        raise CatalogError("Invalid JSON") from exc


def check_schema(data, path):
    schema = decode_json(read_bounded(path))
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise CatalogError(f"{path.name}: invalid JSON Schema") from exc
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER, registry=Registry()
    )
    error = next(validator.iter_errors(data), None)
    if error is not None:
        location = "/".join(str(part) for part in error.absolute_path) or "root"
        # Do not log rejected values: a submission may contain private data.
        raise CatalogError(f"{path.name}: {location} violates {error.validator}")


def plain_text(value, field, max_length):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > max_length
        or value.strip() != value
        or any(
            unicodedata.category(char).startswith("C")
            or unicodedata.category(char) in {"Zl", "Zp"}
            for char in value
        )
    ):
        raise CatalogError(f"{field} must be nonempty, bounded, single-line text")
    return value


def repository_slug(value):
    if (
        not isinstance(value, str)
        or not REPO_PATTERN.fullmatch(value)
        or value.split("/")[1] in {".", ".."}
    ):
        raise CatalogError("Repository must be a GitHub owner/repository, not a URL")
    return value


def relative_path(value, field, max_length=1024):
    plain_text(value, field, max_length)
    if "\\" in value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise CatalogError(f"{field} is not a safe relative path")
    return value


def positive_integer(value, field):
    if type(value) is not int or value < 1:
        raise CatalogError(f"{field} must be a positive integer")
    return value


def validate_cover(project, root):
    """Only locally reviewed raster files can appear in the public gallery."""
    cover = project.get("cover")
    if cover is None:
        return
    filename = cover["image"]
    if not COVER_PATTERN.fullmatch(filename):
        raise CatalogError("Gallery image must be a local PNG, JPG, or WebP filename")
    plain_text(cover["alt"], "gallery image alternative text", 160)
    path = root / "docs/assets/projects" / filename
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise CatalogError("Gallery image must exist inside the community repository")
    data = read_bounded(path, MAX_COVER_BYTES)
    signature_ok = {
        ".png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": data.startswith(b"\xff\xd8\xff"),
        ".webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    }.get(path.suffix, False)
    if not signature_ok:
        raise CatalogError("Gallery image format does not match its file extension")


def load_registry(root=ROOT):
    try:
        data = yaml.load(
            read_bounded(root / "registry/projects.yml"), Loader=RegistryLoader
        )
    except (yaml.YAMLError, RecursionError) as exc:
        raise CatalogError("Invalid registry YAML") from exc
    check_schema(data, root / "registry/projects.schema.json")
    if type(data["schema_version"]) is not int:
        raise CatalogError("Registry schema_version must be an integer")
    seen_names, seen_ids = set(), set()
    for project in data["projects"]:
        repo = repository_slug(project["repository"]).casefold()
        repo_id = positive_integer(project["repository_id"], "repository_id")
        if repo in seen_names or repo_id in seen_ids:
            raise CatalogError("Duplicate repository name or repository ID")
        seen_names.add(repo)
        seen_ids.add(repo_id)
        plain_text(project["name"], "project name", 80)
        plain_text(project["summary"], "project summary", 240)
        if project["category"] not in CATEGORIES:
            raise CatalogError("Unknown project category")
        validate_cover(project, root)
    return data


class NoRedirect(HTTPRedirectHandler):
    """A rename must be reviewed; never follow a redirect or send credentials on it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubClient:
    ENDPOINTS = {"", "/readme", "/license", "/releases/latest", "/issues"}

    def __init__(self, token=None, opener=None):
        self.opener = opener if opener is not None else build_opener(NoRedirect())
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AISciHub-OSS-catalog",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, repo, endpoint="", params=None):
        repo = repository_slug(repo)
        if endpoint not in self.ENDPOINTS:
            raise CatalogError("Unexpected GitHub API endpoint")
        url = f"{API_ROOT}/repos/{repo}{endpoint}"
        if params:
            url += "?" + urlencode(params)
        resource = f"{repo}{endpoint}"
        headers = self.headers.copy()
        while True:
            request = Request(url, headers=headers, method="GET")
            try:
                with self.opener.open(request, timeout=20) as response:
                    if response.getcode() != 200:
                        raise CatalogError(f"{resource}: unexpected HTTP status")
                    body = response.read(MAX_API_BYTES + 1)
                break
            except HTTPError as exc:
                # The Actions token is scoped to its own repository. Public
                # resources are also available anonymously; a scope denial
                # gets one anonymous retry, never a broader credential.
                response_headers = exc.headers or {}
                limited = (
                    response_headers.get("X-RateLimit-Remaining") == "0"
                    or response_headers.get("Retry-After") is not None
                )
                if (
                    "Authorization" in headers
                    and exc.code in {401, 403, 404}
                    and not limited
                ):
                    headers.pop("Authorization")
                    exc.close()
                    continue
                if exc.code == 404 and endpoint == "/releases/latest":
                    return None
                if 300 <= exc.code < 400:
                    raise CatalogError(f"{resource}: redirected; review the repository URL") from exc
                raise CatalogError(f"{resource}: GitHub returned HTTP {exc.code}") from exc
            except (URLError, OSError, ValueError) as exc:
                raise CatalogError(f"{resource}: could not read the GitHub API") from exc
        if len(body) > MAX_API_BYTES:
            raise CatalogError(f"{resource}: API response exceeds the size limit")
        return decode_json(body)


def require_object(value, resource):
    if not isinstance(value, dict):
        raise CatalogError(f"{resource}: expected a GitHub JSON object")
    return value


def license_id(value):
    value = value.get("license")
    return value.get("spdx_id") if isinstance(value, dict) else None


def file_path(data, resource):
    require_object(data, resource)
    if data.get("type") != "file" or type(data.get("size")) is not int or data["size"] <= 0:
        raise CatalogError(f"{resource}: expected a nonempty file")
    return relative_path(data.get("path"), resource)


def verify_repository(client, project):
    """Check public identity, README and the approved license, without running code."""
    repo = repository_slug(project["repository"])
    data = require_object(client.get(repo), repo)
    if (
        not isinstance(data.get("full_name"), str)
        or data["full_name"].casefold() != repo.casefold()
        or type(data.get("id")) is not int
        or data["id"] != project["repository_id"]
    ):
        raise CatalogError(f"{repo}: repository identity changed; review the registry")
    if (
        data.get("private") is not False
        or data.get("visibility") != "public"
        or data.get("archived") is not False
        or data.get("disabled") is not False
    ):
        raise CatalogError(f"{repo}: repository must be public, enabled and unarchived")
    if license_id(data) != project["license"]:
        raise CatalogError(f"{repo}: GitHub-detected license differs from approved license")

    readme_path = file_path(client.get(repo, "/readme"), f"{repo} README")
    license_data = require_object(client.get(repo, "/license"), f"{repo} license")
    license_path = file_path(license_data, f"{repo} license")
    if license_id(license_data) != project["license"]:
        raise CatalogError(f"{repo}: license file does not match approved SPDX identifier")
    language = data.get("language")
    if language is not None:
        plain_text(language, f"{repo} language", 80)
    if type(data.get("has_issues")) is not bool:
        raise CatalogError(f"{repo}: missing issue-tracker status")
    return {
        "repository": repo,
        "repository_id": project["repository_id"],
        "visibility": "public",
        "language": language,
        "default_branch": relative_path(data.get("default_branch"), f"{repo} branch", 255),
        "readme_path": readme_path,
        "license": project["license"],
        "license_path": license_path,
        "issues_enabled": data["has_issues"],
    }


def latest_release(client, repo):
    data = client.get(repo, "/releases/latest")
    if data is None:
        return None
    require_object(data, f"{repo} release")
    if data.get("draft") is not False or data.get("prerelease") is not False:
        raise CatalogError(f"{repo}: latest release is not a published stable release")
    tag = relative_path(data.get("tag_name"), f"{repo} release tag", 255)
    try:
        published = datetime.strptime(data["published_at"], "%Y-%m-%dT%H:%M:%SZ")
    except (KeyError, ValueError, TypeError) as exc:
        raise CatalogError(f"{repo}: invalid release publication time") from exc
    return {"tag": tag, "published_on": published.date().isoformat()}


def good_first_issues(client, repo):
    # GitHub's Issues API can return pull requests; do not list those as issues.
    rows = client.get(
        repo,
        "/issues",
        {
            "state": "open",
            "labels": "good first issue",
            "sort": "created",
            "direction": "desc",
            "per_page": 20,
        },
    )
    if not isinstance(rows, list):
        raise CatalogError(f"{repo}: invalid issue list")
    numbers = set()
    for row in rows:
        require_object(row, f"{repo} issue")
        if "pull_request" in row or row.get("state") != "open":
            continue
        labels = row.get("labels")
        if not isinstance(labels, list):
            raise CatalogError(f"{repo}: invalid issue labels")
        if not any(
            isinstance(label, dict)
            and isinstance(label.get("name"), str)
            and label["name"].casefold() == "good first issue"
            for label in labels
        ):
            continue
        numbers.add(positive_integer(row.get("number"), f"{repo} issue number"))
    return sorted(numbers, reverse=True)[:3]


def collect_metadata(registry, client, checked_on=None):
    projects = []
    for project in sorted(registry["projects"], key=lambda entry: entry["repository"].casefold()):
        metadata = verify_repository(client, project)
        repo = project["repository"]
        metadata["latest_release"] = latest_release(client, repo)
        metadata["good_first_issues"] = (
            good_first_issues(client, repo) if metadata["issues_enabled"] else []
        )
        projects.append(metadata)
    return {
        "schema_version": 1,
        "checked_on": checked_on or datetime.now(timezone.utc).date().isoformat(),
        "projects": projects,
    }


def validate_snapshot(registry, snapshot, root=ROOT):
    check_schema(snapshot, root / "registry/metadata.schema.json")
    if type(snapshot["schema_version"]) is not int:
        raise CatalogError("Metadata schema_version must be an integer")
    expected = {project["repository"]: project for project in registry["projects"]}
    seen = set()
    for item in snapshot["projects"]:
        repo = repository_slug(item["repository"])
        if repo in seen or repo not in expected:
            raise CatalogError("Metadata must contain exactly the approved repositories")
        approved = expected[repo]
        if (
            positive_integer(item["repository_id"], "repository_id") != approved["repository_id"]
            or item["license"] != approved["license"]
        ):
            raise CatalogError(f"{repo}: metadata identity or license disagrees with registry")
        seen.add(repo)
        if item["language"] is not None:
            plain_text(item["language"], "language", 80)
        relative_path(item["default_branch"], "default branch", 255)
        relative_path(item["readme_path"], "README path")
        relative_path(item["license_path"], "license path")
        if item["latest_release"] is not None:
            relative_path(item["latest_release"]["tag"], "release tag", 255)
        for number in item["good_first_issues"]:
            positive_integer(number, "issue number")
        if not item["issues_enabled"] and item["good_first_issues"]:
            raise CatalogError(f"{repo}: issues are disabled")
    if seen != set(expected):
        raise CatalogError("Metadata is missing approved repositories; run refresh")


# Render free text as text, not HTML, Markdown syntax, table separators or mentions.
# All link targets below are built from validated repository names and encoded paths.
INLINE_ENTITIES = str.maketrans(
    {char: f"&#{ord(char)};" for char in "&<>`*_~[]()!|\\@#:$"}
)


def inline(value):
    # Also neutralize GitHub's extended www. autolink syntax.
    return re.sub(r"www\.", lambda match: match[0][:-1] + "&#46;", value.translate(INLINE_ENTITIES), flags=re.I)


def render_catalog(registry, snapshot):
    metadata = {entry["repository"]: entry for entry in snapshot["projects"]}
    count = len(registry["projects"])
    project_count = "1 project" if count == 1 else f"{count} projects"
    lines = [
        "# Project catalog",
        "",
        "<!-- Generated by scripts/catalog.py; edit registry/projects.yml, not this file. -->",
        "",
        f"**{project_count}** · GitHub metadata checked {snapshot['checked_on']} (UTC).",
        "",
        "Browse projects by area, read their source, and contribute in their own repositories.",
        "The latest release is GitHub's latest published stable release. Issue links point to",
        "open issues labeled `good first issue`; each project also links to its filtered issue list.",
        "",
        "[Submit a project](CONTRIBUTING.md#submit-a-project) · "
        "[Eligibility standards](PROJECT_ELIGIBILITY.md) · [Contributing](CONTRIBUTING.md)",
        "",
    ]
    if not registry["projects"]:
        lines.extend(["No projects have been listed yet.", ""])
    for category, title in CATEGORIES.items():
        projects = sorted(
            (p for p in registry["projects"] if p["category"] == category),
            key=lambda p: (p["name"].casefold(), p["repository"].casefold()),
        )
        if not projects:
            continue
        lines.extend([
            f"## {title}",
            "",
            "| Project | What it does | Language | License | Latest GitHub release | Good first issues |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for project in projects:
            repo = project["repository"]
            item = metadata[repo]
            base = f"https://github.com/{repo}"
            license_link = f"[{inline(item['license'])}]({base}/blob/HEAD/{quote(item['license_path'], safe='/')})"
            release = item["latest_release"]
            if release is None:
                release_link = f"[No stable release]({base}/releases)"
            else:
                release_link = (
                    f"[{inline(release['tag'])}]({base}/releases/tag/{quote(release['tag'], safe='')})"
                    f" ({release['published_on']})"
                )
            if item["issues_enabled"]:
                query = urlencode({"q": 'is:issue is:open label:"good first issue"'})
                issues = [
                    f"[#{number}]({base}/issues/{number})"
                    for number in item["good_first_issues"]
                ]
                if not issues:
                    issues.append("None listed")
                issues.append(f"[Browse labeled issues]({base}/issues?{query})")
                issue_links = " · ".join(issues)
            else:
                issue_links = "Issues disabled"
            cells = [
                f"[{inline(project['name'])}]({base})",
                inline(project["summary"]),
                inline(item["language"]) if item["language"] else "Not detected",
                license_link,
                release_link,
                issue_links,
            ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    lines.extend([
        "Projects remain under their respective maintainers' ownership. Inclusion is",
        "not an endorsement or security audit. The catalog is a reviewed snapshot, not a live feed.",
        "",
    ])
    return "\n".join(lines)


def atomic_write(path, content):
    # A failed API check never reaches the write phase; individual files are
    # replaced atomically once all complete outputs have been prepared.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temp_path = Path(stream.name)
        try:
            stream.write(content)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
    try:
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def rendered_outputs(root, registry, snapshot):
    return [
        (root / "PROJECTS.md", render_catalog(registry, snapshot)),
        (root / "docs/index.html", render_gallery(registry, snapshot, CATEGORIES)),
    ]


def main(argv=None, root=ROOT, client_factory=GitHubClient):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["check", "validate", "refresh", "render"],
        help="check committed outputs offline; validate live eligibility; refresh from GitHub; or render offline",
    )
    args = parser.parse_args(argv)
    try:
        registry = load_registry(root)
        snapshot_file = root / "registry/metadata.json"
        if args.command in {"check", "render"}:
            snapshot = decode_json(read_bounded(snapshot_file))
            validate_snapshot(registry, snapshot, root)
            for path, content in rendered_outputs(root, registry, snapshot):
                if args.command == "check":
                    if read_bounded(path) != content.encode("utf-8"):
                        raise CatalogError(f"{path.relative_to(root)} is out of date; run render")
                else:
                    atomic_write(path, content)
        else:
            client = client_factory(token=os.environ.get("GITHUB_TOKEN"))
            if args.command == "validate":
                for project in registry["projects"]:
                    verify_repository(client, project)
            else:
                snapshot = collect_metadata(registry, client)
                validate_snapshot(registry, snapshot, root)
                outputs = rendered_outputs(root, registry, snapshot)
                atomic_write(
                    snapshot_file, json.dumps(snapshot, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
                )
                for path, content in outputs:
                    atomic_write(path, content)
        print(f"{args.command}: {len(registry['projects'])} projects OK")
        return 0
    except (CatalogError, OSError, UnicodeError, RecursionError) as exc:
        # Single line, no GitHub workflow commands or raw response payloads.
        print("Catalog error: " + " ".join(str(exc).split())[:500], file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
