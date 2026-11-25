# Project registry

`projects.yml` is the maintainer-reviewed source of catalog membership.
`projects.schema.json` defines its structure; `scripts/catalog.py` adds
checks for canonical GitHub paths, duplicate identities, and safe text.

## Fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Registry format version; currently `1` |
| `projects` | Array of approved project records |
| `name` | Display name, 1–80 characters, single line |
| `repository` | Canonical GitHub `OWNER/REPOSITORY`, without URL, branch, or trailing slash |
| `repository_id` | Public integer repository ID from GitHub; prevents silently accepting a different repository at a reused path |
| `category` | One of the project areas below |
| `summary` | Reviewed plain-text description, 1–240 characters, single line |
| `license` | Expected GitHub-detected SPDX ID of the reviewed open-source license |
| `cover` (optional) | Reviewed local raster image filename and single-line alternative text for the visual gallery |

Example record (illustrative values; replace with verified data):

```yaml
- name: Example Tool
  repository: example-owner/example-tool
  repository_id: 123456789
  category: developer-tools
  summary: A command-line utility for working with example data.
  license: MIT
```

The repository can live under any public GitHub user or organization. To get
the repository ID and detected license, read its [public REST metadata](https://docs.github.com/en/rest/repos/repos#get-a-repository).
With GitHub CLI installed, the equivalent read-only command is:

```bash
gh api repos/OWNER/REPOSITORY --jq '{repository: .full_name, id: .id, license: .license.spdx_id, visibility: .visibility}'
```

Check the actual README and license file too. GitHub's license detection
is not a substitute for reading the license.

For an optional project cover, add:

```yaml
  cover:
    image: example-tool.png
    alt: Public preview of Example Tool.
```

Save the image under `docs/assets/projects/`. The checker accepts only
local PNG, JPG, or WebP filenames, matching raster signatures, and files
up to 4 MiB. Missing or externally hosted images are rejected. Projects
without covers receive a neutral gallery placeholder. Record image source
and permission or license in [gallery-assets.md](gallery-assets.md).
The issue form does not request image URLs or attachments; maintainers
choose and review public artwork separately.

## Categories

| Registry key | Display title |
| --- | --- |
| `ai-and-automation` | AI & automation |
| `apps-and-utilities` | Apps & utilities |
| `civic-tech` | Civic tech & accessibility |
| `developer-tools` | Developer tools & security |
| `scientific-computing` | Scientific computing & data |
| `web-and-browser` | Web & browser |

The schema permits common OSI-approved license IDs, including GitHub's
legacy GPL-family IDs. Unknown or proprietary licenses and `NOASSERTION`
are not accepted automatically. Expand the schema only after a human
reviews the additional OSI-approved license.

## Generated files

`metadata.json` is a dated snapshot of GitHub's public repository identity,
visibility, primary language, default branch, README and license paths,
license identifier, and issue-tracker status. It also contains GitHub's
latest stable release tag and publication date (or null), and up to three
open issue numbers labeled `good first issue` from the newest 20 returned
records, excluding pull requests. The catalog always links to the filtered
issue list where issues are enabled; a repository can be listed without
a release or a matching issue.

Only these allowlisted fields are persisted. The collector never persists
raw API payloads, contributor details, issue titles, bodies, or release
notes. It never uses an API-provided URL as a link target: links use the
validated GitHub repository path and encoded file/tag paths.

Run `python scripts/catalog.py refresh` from the community repo to fetch and
generate `metadata.json`, `PROJECTS.md`, and the static gallery at
`docs/index.html`. The gallery displays the reviewed registry order, not
a popularity ranking. The refresh fails on missing,
unavailable, renamed, archived, or license-mismatched repositories and does
not write new files if an API check fails. A reviewed PR publishes the
complete snapshot. Use `check` to validate all generated files offline.

The schema caps the initial registry at 100 projects to bound API usage
(five endpoint reads per project on a refresh, with at most one anonymous
retry per scope-denied request). The reader bounds file and response sizes.
If the community outgrows these limits, review API rate limits and capacity
before raising them.

## Seed project provenance

The initial three repositories and AirWater AI were checked via GitHub's
public repository, README, and license endpoints on November 25, 2026.
All four were public,
enabled, unarchived, and had nonempty READMEs and license files detected as MIT.
The metadata snapshot and generated project catalog are based on
the live collector, not manually invented release or issue values.

| Project | Public repository | License |
| --- | --- | --- |
| CookieGuard AI | [aiscihub/cookieguard-ai](https://github.com/aiscihub/cookieguard-ai) | [MIT](https://github.com/aiscihub/cookieguard-ai/blob/HEAD/LICENSE) |
| BenefitStep | [aiscihub/benefitstep](https://github.com/aiscihub/benefitstep) | [MIT](https://github.com/aiscihub/benefitstep/blob/HEAD/LICENSE) |
| PocketStop | [aiscihub/PocketStop](https://github.com/aiscihub/PocketStop) | [MIT](https://github.com/aiscihub/PocketStop/blob/HEAD/LICENSE) |
| AirWater AI | [aiscihub/airwater_app](https://github.com/aiscihub/airwater_app) | [MIT](https://github.com/aiscihub/airwater_app/blob/HEAD/LICENSE) |
