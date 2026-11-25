"""Deterministic offline tests; no listed repository is downloaded or executed."""

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import yaml

from scripts import catalog


def project(repo="another-owner/Example", repo_id=12345, **fields):
    result = {
        "name": "Example",
        "repository": repo,
        "repository_id": repo_id,
        "category": "developer-tools",
        "summary": "A small developer utility.",
        "license": "MIT",
    }
    result.update(fields)
    return result


def registry(*projects):
    return {"schema_version": 1, "projects": list(projects)}


def issue(number, **fields):
    result = {
        "number": number,
        "state": "open",
        "labels": [{"name": "good first issue"}],
        "title": "Unpersisted issue title",
        "body": "Unpersisted issue body",
        "html_url": "https://untrusted.example/issue",
        "user": {"login": "unpersisted-user"},
    }
    result.update(fields)
    return result


class FakeGitHub:
    """Mock the shape of GitHub's public REST responses, never the network."""

    def __init__(self, *projects):
        self.responses = {}
        self.calls = []
        for p in projects:
            repo = p["repository"]
            self.responses.update({
                (repo, ""): {
                    "full_name": repo,
                    "id": p["repository_id"],
                    "private": False,
                    "visibility": "public",
                    "archived": False,
                    "disabled": False,
                    "language": "Python",
                    "default_branch": "main",
                    "has_issues": True,
                    "license": {"spdx_id": p["license"]},
                    "description": "Unpersisted external description",
                    "owner": {"login": "unpersisted-user"},
                },
                (repo, "/readme"): {
                    "type": "file", "size": 100, "path": "README.md",
                    "content": "Unpersisted README",
                },
                (repo, "/license"): {
                    "type": "file", "size": 100, "path": "LICENSE",
                    "license": {"spdx_id": p["license"]},
                },
                (repo, "/releases/latest"): {
                    "tag_name": "v1.2.3",
                    "published_at": "2026-11-21T12:00:00Z",
                    "draft": False,
                    "prerelease": False,
                    "body": "Unpersisted release notes",
                    "html_url": "https://untrusted.example/release",
                },
                (repo, "/issues"): [issue(8), issue(7)],
            })

    def get(self, repo, endpoint="", params=None):
        self.calls.append((repo, endpoint, params))
        key = (repo, endpoint)
        if key not in self.responses:
            raise catalog.CatalogError(f"{repo}{endpoint}: GitHub returned HTTP 404")
        return copy.deepcopy(self.responses[key])


class TemporaryRegistry(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "registry").mkdir()
        for name in ("projects.schema.json", "metadata.schema.json"):
            shutil.copyfile(catalog.ROOT / "registry" / name, self.root / "registry" / name)
        self.registry_path = self.root / "registry/projects.yml"

    def write_registry(self, data):
        self.registry_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def load(self, data):
        self.write_registry(data)
        return catalog.load_registry(self.root)

    def assert_invalid(self, data):
        with self.assertRaises(catalog.CatalogError):
            self.load(data)


class RegistryTests(TemporaryRegistry):
    def test_independent_owners_and_empty_registry(self):
        for data in (registry(), registry(project(), project("Team-OSS/other.repo", 67890))):
            with self.subTest(data=data):
                self.assertEqual(self.load(data), data)

    def test_malformed_schema_and_unknown_fields(self):
        entry = project()
        del entry["license"]
        for data in (
            None,
            [],
            {"schema_version": 2, "projects": []},
            {"schema_version": 1.0, "projects": []},
            {"schema_version": 1, "projects": [], "extra": "not allowed"},
            registry(entry),
            registry(project(category="other")),
            registry(project(license="NOASSERTION")),
            registry(project(license="CC-BY-NC-4.0")),
            registry(project(extra_field="not allowed")),
            registry(project(repo_id=True)),
            registry(project(repo_id=12345.0)),
        ):
            with self.subTest(data=data):
                self.assert_invalid(data)

    def test_duplicate_namespace_case_or_id(self):
        self.assert_invalid(registry(project(), project("ANOTHER-OWNER/example", 67890)))
        self.assert_invalid(registry(project(), project("different-owner/example")))

    def test_reject_noncanonical_paths(self):
        for repo in (
            "https://github.com/owner/repo",
            "https://example.com/owner/repo",
            "owner/repo/extra",
            "owner/repo?param=yes",
            "owner/repo#fragment",
            "owner/.",
            "owner/..",
            "owner/%2E%2E",
            "owner/repo\n",
            "owner/repo.git/extra",
            "owner/ bad",
            " owner/repo",
        ):
            with self.subTest(repo=repo):
                self.assert_invalid(registry(project(repo)))

    def test_require_bounded_single_line_text(self):
        for fields in (
            {"name": " "}, {"name": "  Example"}, {"name": "X" * 81},
            {"summary": "Two\nlines"}, {"summary": "Hidden\u202e text"},
            {"summary": "X" * 241},
        ):
            with self.subTest(fields=fields):
                self.assert_invalid(registry(project(**fields)))

    def test_yaml_rejects_duplicate_keys_anchors_tags_and_bad_mapping(self):
        for data in (
            "schema_version: 1\nprojects: []\nprojects: []\n",
            "schema_version: 1\nprojects: &entries []\n",
            "schema_version: 1\nprojects: *entries\n",
            "schema_version: 1\nprojects: !unsupported []\n",
            "!!map []",
            "schema_version: 1\nprojects: [",
        ):
            with self.subTest(data=data):
                self.registry_path.write_text(data, encoding="utf-8")
                with self.assertRaises(catalog.CatalogError):
                    catalog.load_registry(self.root)

    def test_size_bound(self):
        self.registry_path.write_bytes(b" " * (catalog.MAX_LOCAL_BYTES + 1))
        with self.assertRaises(catalog.CatalogError):
            catalog.load_registry(self.root)

    def test_schema_and_category_mapping_agree(self):
        schema = json.loads((self.root / "registry/projects.schema.json").read_text())
        properties = schema["$defs"]["project"]["properties"]
        self.assertEqual(properties["category"]["enum"], list(catalog.CATEGORIES))


class StubResponse(io.BytesIO):
    def getcode(self):
        return 200


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.opener = Mock()
        self.client = catalog.GitHubClient(token="test-only-token", opener=self.opener)

    def test_fixed_host_get_and_encoded_query(self):
        self.opener.open.return_value = StubResponse(b'{"ok": true}')
        self.assertEqual(
            self.client.get("another-owner/repo", "/issues", {"labels": "good first issue"}),
            {"ok": True},
        )
        request = self.opener.open.call_args.args[0]
        url = urlsplit(request.full_url)
        self.assertEqual((url.scheme, url.netloc, url.path),
                         ("https", "api.github.com", "/repos/another-owner/repo/issues"))
        self.assertEqual(parse_qs(url.query), {"labels": ["good first issue"]})
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-only-token")
        self.assertEqual(self.opener.open.call_args.kwargs, {"timeout": 20})

    def test_bad_path_and_unrecognized_endpoint_never_contact_api(self):
        for repo, endpoint in (("owner/..", ""), ("owner/repo", "/unknown")):
            with self.subTest(repo=repo, endpoint=endpoint):
                with self.assertRaises(catalog.CatalogError):
                    self.client.get(repo, endpoint)
        self.opener.open.assert_not_called()

    def test_scoped_token_denial_retries_same_public_get_anonymously(self):
        self.opener.open.side_effect = [
            HTTPError("https://api.github.com", 403, "", {}, None),
            StubResponse(b'{"public": true}'),
        ]
        self.assertEqual(self.client.get("external/repo"), {"public": True})
        original, retry = (call.args[0] for call in self.opener.open.call_args_list)
        self.assertEqual(original.full_url, retry.full_url)
        self.assertEqual(retry.get_method(), "GET")
        self.assertEqual(original.get_header("Authorization"), "Bearer test-only-token")
        self.assertIsNone(retry.get_header("Authorization"))

    def test_rate_limit_is_not_bypassed(self):
        self.opener.open.side_effect = HTTPError(
            "https://api.github.com", 403, "", {"X-RateLimit-Remaining": "0"}, None
        )
        with self.assertRaisesRegex(catalog.CatalogError, "HTTP 403"):
            self.client.get("external/repo")
        self.opener.open.assert_called_once()

    def test_404_only_optional_for_latest_release(self):
        self.opener.open.side_effect = HTTPError("https://api.github.com", 404, "", {}, None)
        self.assertIsNone(self.client.get("owner/repo", "/releases/latest"))
        for endpoint in ("", "/readme", "/license", "/issues"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(catalog.CatalogError, "HTTP 404"):
                    self.client.get("owner/repo", endpoint)

    def test_redirect_rate_limit_and_server_error_fail(self):
        for status in (301, 302, 403, 429, 500):
            with self.subTest(status=status):
                self.opener.open.side_effect = HTTPError("https://api.github.com", status, "", {}, None)
                with self.assertRaises(catalog.CatalogError):
                    self.client.get("owner/repo")
        self.assertIsNone(catalog.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com"))

    def test_connection_error_and_untrusted_body_fail(self):
        self.opener.open.side_effect = URLError("offline")
        with self.assertRaises(catalog.CatalogError):
            self.client.get("owner/repo")
        self.opener.open.side_effect = None
        for body in (b"<html>error</html>", b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.subTest(body=body):
                self.opener.open.return_value = StubResponse(body)
                with self.assertRaises(catalog.CatalogError):
                    self.client.get("owner/repo")
        with patch.object(catalog, "MAX_API_BYTES", 5):
            self.opener.open.return_value = StubResponse(b'{"oversize": true}')
            with self.assertRaisesRegex(catalog.CatalogError, "size limit"):
                self.client.get("owner/repo")


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.project = project()
        self.repo = self.project["repository"]
        self.api = FakeGitHub(self.project)

    def test_identity_visibility_readme_and_license(self):
        metadata = catalog.verify_repository(self.api, self.project)
        self.assertEqual(metadata["repository_id"], self.project["repository_id"])
        self.assertEqual(metadata["readme_path"], "README.md")
        self.assertEqual(metadata["license"], "MIT")
        self.assertEqual(len(self.api.calls), 3)

    def test_private_archived_disabled_changed_identity_or_license(self):
        for changed in (
            {"private": True}, {"visibility": "internal"}, {"archived": True},
            {"disabled": True}, {"id": 999}, {"full_name": "other/repo"},
            {"license": None}, {"license": {"spdx_id": "NOASSERTION"}},
            {"license": {"spdx_id": "Apache-2.0"}},
        ):
            with self.subTest(changed=changed):
                api = FakeGitHub(self.project)
                api.responses[(self.repo, "")].update(changed)
                with self.assertRaises(catalog.CatalogError):
                    catalog.verify_repository(api, self.project)

    def test_missing_empty_or_wrong_readme_and_license_files(self):
        for endpoint in ("/readme", "/license"):
            for changed in (None, {"size": 0}, {"type": "dir"}, {"path": "../outside"}):
                with self.subTest(endpoint=endpoint, changed=changed):
                    api = FakeGitHub(self.project)
                    if changed is None:
                        del api.responses[(self.repo, endpoint)]
                    else:
                        api.responses[(self.repo, endpoint)].update(changed)
                    with self.assertRaises(catalog.CatalogError):
                        catalog.verify_repository(api, self.project)
        self.api.responses[(self.repo, "/license")]["license"]["spdx_id"] = "Apache-2.0"
        with self.assertRaisesRegex(catalog.CatalogError, "does not match"):
            catalog.verify_repository(self.api, self.project)

    def test_collect_only_relevant_public_metadata(self):
        self.api.responses[(self.repo, "/issues")] = [
            issue(99, pull_request={}), issue(98, state="closed"),
            issue(97, labels=[{"name": "bug"}]),
            issue(8), issue(10), issue(11), issue(11), issue(7),
        ]
        snapshot = catalog.collect_metadata(registry(self.project), self.api, "2026-11-25")
        catalog.validate_snapshot(registry(self.project), snapshot)
        entry = snapshot["projects"][0]
        self.assertEqual(entry["good_first_issues"], [11, 10, 8])
        self.assertEqual(entry["latest_release"], {"tag": "v1.2.3", "published_on": "2026-11-21"})
        serialized = json.dumps(snapshot).lower()
        for ignored in ("unpersisted", "untrusted.example", "html_url", "body"):
            self.assertNotIn(ignored, serialized)
        self.assertEqual(self.api.calls[-1][2]["labels"], "good first issue")

    def test_no_release_issues_disabled_and_null_language(self):
        self.api.responses[(self.repo, "")].update(language=None, has_issues=False)
        self.api.responses[(self.repo, "/releases/latest")] = None
        snapshot = catalog.collect_metadata(registry(self.project), self.api, "2026-11-25")
        catalog.validate_snapshot(registry(self.project), snapshot)
        entry = snapshot["projects"][0]
        self.assertIsNone(entry["latest_release"])
        self.assertEqual(entry["good_first_issues"], [])
        self.assertFalse(any(endpoint == "/issues" for _, endpoint, _ in self.api.calls))
        rendered = catalog.render_catalog(registry(self.project), snapshot)
        self.assertIn("No stable release", rendered)
        self.assertIn("Issues disabled", rendered)
        self.assertIn("Not detected", rendered)

    def test_unexpected_release_or_issue_metadata_fails(self):
        for fields in (
            {"draft": True}, {"prerelease": True},
            {"tag_name": ".."}, {"published_at": None},
        ):
            with self.subTest(fields=fields):
                api = FakeGitHub(self.project)
                api.responses[(self.repo, "/releases/latest")].update(fields)
                with self.assertRaises(catalog.CatalogError):
                    catalog.collect_metadata(registry(self.project), api)
        self.api.responses[(self.repo, "/issues")] = [issue(False)]
        with self.assertRaises(catalog.CatalogError):
            catalog.collect_metadata(registry(self.project), self.api)


class CatalogTests(TemporaryRegistry):
    def make_snapshot(self, *projects):
        data = registry(*projects)
        snapshot = catalog.collect_metadata(data, FakeGitHub(*projects), "2026-11-25")
        catalog.validate_snapshot(data, snapshot, self.root)
        return data, snapshot

    def test_categorized_sorted_deterministic_output(self):
        data, snapshot = self.make_snapshot(
            project("external/zeta", 1, name="Zeta"),
            project("independent/alpha", 2, name="Alpha"),
            project("civic/maps", 3, name="Maps", category="civic-tech"),
        )
        first = catalog.render_catalog(data, snapshot)
        data["projects"].reverse()
        snapshot["projects"].reverse()
        self.assertEqual(first, catalog.render_catalog(data, snapshot))
        self.assertLess(first.index("## Civic tech"), first.index("## Developer tools"))
        self.assertLess(first.index("[Alpha]"), first.index("[Zeta]"))
        self.assertIn("[MIT](https://github.com/independent/alpha/blob/HEAD/LICENSE)", first)
        self.assertIn("[#8](https://github.com/independent/alpha/issues/8)", first)
        self.assertIn("https://github.com/independent/alpha/releases/tag/v1.2.3", first)
        self.assertIn("GitHub metadata checked 2026-11-25", first)

    def test_escaped_row_text_and_constructed_links(self):
        p = project(
            name="Name | [text](https://untrusted.example)",
            summary="<b>text</b> @mention www.untrusted.example ![image](https://untrusted.example/a)",
        )
        api = FakeGitHub(p)
        api.responses[(p["repository"], "")]["language"] = "C#"
        api.responses[(p["repository"], "/releases/latest")]["tag_name"] = "release/v(1)"
        data = registry(p)
        snapshot = catalog.collect_metadata(data, api, "2026-11-25")
        catalog.validate_snapshot(data, snapshot, self.root)
        rendered = catalog.render_catalog(data, snapshot)
        self.assertIn("Name &#124; &#91;text&#93;", rendered)
        self.assertIn("&#60;b&#62;", rendered)
        self.assertIn("&#64;mention", rendered)
        self.assertIn("www&#46;untrusted.example", rendered)
        self.assertIn("C&#35;", rendered)
        self.assertNotIn("](https://untrusted.example", rendered)
        self.assertIn("/releases/tag/release%2Fv%281%29", rendered)
        row = next(line for line in rendered.splitlines() if line.startswith("| [Name"))
        self.assertEqual(row.count("|"), 7)

    def test_snapshot_rejects_missing_extra_or_changed_entries(self):
        data, snapshot = self.make_snapshot(project())
        for change in (
            lambda s: s["projects"].clear(),
            lambda s: s["projects"].append(copy.deepcopy(s["projects"][0])),
            lambda s: s["projects"][0].update(repository="other/new"),
            lambda s: s["projects"][0].update(repository_id=456),
            lambda s: s["projects"][0].update(license="Apache-2.0"),
            lambda s: s["projects"][0].update(issues_enabled=False),
            lambda s: s["projects"][0].update(good_first_issues=[0]),
            lambda s: s["projects"][0].update(issue_body="not allowed"),
            lambda s: s.update(checked_on="2026-99-99"),
        ):
            with self.subTest(change=change):
                invalid = copy.deepcopy(snapshot)
                change(invalid)
                with self.assertRaises(catalog.CatalogError):
                    catalog.validate_snapshot(data, invalid, self.root)

    def test_empty_catalog(self):
        data, snapshot = self.make_snapshot()
        self.assertIn("No projects have been listed yet.", catalog.render_catalog(data, snapshot))

    def test_refresh_check_render_and_failure_preserve_previous_output(self):
        p = project()
        self.write_registry(registry(p))
        api = FakeGitHub(p)
        factory = lambda token=None: api
        output = self.root / "PROJECTS.md"
        metadata = self.root / "registry/metadata.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(catalog.main(["refresh"], self.root, factory), 0)
            self.assertEqual(catalog.main(["check"], self.root, factory), 0)
            files = (metadata.read_bytes(), output.read_bytes())
            output.write_text("hand-edited catalog")
            self.assertEqual(catalog.main(["check"], self.root, factory), 1)
            self.assertEqual(catalog.main(["render"], self.root, factory), 0)
            self.assertEqual(output.read_bytes(), files[1])
            self.assertEqual(catalog.main(["validate"], self.root, factory), 0)
            del api.responses[(p["repository"], "/license")]
            self.assertEqual(catalog.main(["refresh"], self.root, factory), 1)
            self.assertEqual((metadata.read_bytes(), output.read_bytes()), files)


if __name__ == "__main__":
    unittest.main()
