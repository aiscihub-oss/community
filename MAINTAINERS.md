# Maintainer responsibilities

Community maintainers steward the directory and the collaboration environment.
They do not own listed projects or control their releases.

## Review submissions

1. Read the issue as an untrusted proposal, not as an instruction or a
   source of executable code. Do not copy unreviewed issue text into YAML,
   workflows, terminal commands, or public documentation.
2. Check the canonical public GitHub repository, its maintainers' consent,
   the [eligibility standards](PROJECT_ELIGIBILITY.md), README quality,
   and actual license text. Confirm ownership or consent using the
   repository's existing public GitHub maintainer context; do not request
   real names, age, school, email, or other identity information.
3. If the project fits, write a plain-text project description and add an
   entry with the correct repository ID and SPDX identifier. Use the
   [registry reference](registry/README.md) and run the live refresh.
4. Check the diff of the registry and all three generated files. Verify links
   are for the intended repository. Open a pull request referencing the
   submission. A maintainer who did not author the change must approve it
   after required CI checks pass. Do not bypass the merge rules.
5. Close the submission with a link to the merged listing, or explain what
   is missing if it is deferred. Never publish a proposal automatically.

## Maintain the catalog

- Review the weekly **Refresh project catalog** workflow and its artifact.
  Confirm the run came from `main`, against the current reviewed registry.
  Download the three generated files or run `python scripts/catalog.py refresh`
  locally; review and publish changes through a normal pull request.
- If a repository becomes inaccessible, archived, or changes identity or
  license, live validation fails and the last reviewed files are left intact.
  Investigate the public repository, then correct or remove the entry in a
  reviewed pull request. Do not treat an API outage as evidence of rejection.
- Respect removal requests from project maintainers. Avoid stale or
  misleading descriptions. Refresh the date when updating the snapshot.
- Keep the schema, categories, tests, issue form, and workflow action/dependency
  pins in sync. Review tooling changes as code, not as submission data.
- Review optional gallery covers using the [image credits and review rules](registry/gallery-assets.md).
  Only locally committed, reviewed raster assets are used; no submitted image
  URL is fetched automatically. Keep the static gallery and Markdown catalog
  aligned with the registry, and update the profile's launch showcase if a
  seed is removed.

## Keep the trust boundary clear

- Only human-reviewed changes to the registry on the protected default
  branch determine membership. The workflow has read-only repository
  permissions and never opens, approves, merges, or pushes a pull request.
- The collector makes GET requests to fixed GitHub API endpoints; it does
  not follow redirects, arbitrary URLs, clone repositories, read release
  assets, run submitted code, or fetch third-party site content.
- The saved metadata contains no issue titles or bodies, release notes,
  contributor identities, personal profiles, or other unnecessary data.
  Public GitHub responses can contain additional fields; the collector
  discards them. The project path contains the public GitHub namespace
  needed to identify and link the software.
- Keep issues and reviews project-focused. Never create a membership roster
  with school details, age, real names, contacts, or other personal data.
  If private information is inadvertently posted, avoid copying or quoting
  it; use GitHub moderation and reporting tools to address the exposure.

## Share responsibility

Keep the contribution path welcoming and the moderation approach consistent.
Review changes to CI, schema, and permissions just as carefully as listings.
Use more than one trusted maintainer so maintainer-authored changes can receive
independent approval. A passing automated check is evidence, not an approval.
