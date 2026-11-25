# Contributing to AISciHub OSS

## Contribute to a listed project

Use the [catalog](PROJECTS.md) to find a project. Read its README and contribution
instructions, then work in that project's own issues and pull requests.
Ask before taking on a large change, keep changes focused, explain your
test results, and be respectful in review. Project maintainers decide what
to accept; the community does not manage their repositories.

## Submit a project

The community is currently publishing its initial seed catalog. The issue
form will become available when submissions open, after the review rules
are activated. The process below describes how submissions will work.

1. Check the [project eligibility standards](PROJECT_ELIGIBILITY.md).
   Make sure the repository's maintainers are comfortable with being listed.
2. Open the [project submission form](https://github.com/aiscihub-oss/community/issues/new?template=project-submission.yml).
   Supply the public GitHub repository URL, project name, area, short
   description, and license. Share no personal information.
3. A community maintainer will review the repository and may ask for
   project-level clarification or documentation improvements. Submissions
   are reviewed for suitability, not ranked against one another.
4. If eligible, a community maintainer prepares a registry pull request (or
   asks you to prepare one). The maintainer checks the GitHub repository ID
   and detected license, and runs the metadata refresh. Another maintainer
   must review and approve a maintainer-authored pull request.
5. The listing is published when a human-approved pull request with passing
   checks is merged into `main`. Opening an issue or passing automated checks
   does not publish a project.

## Improve the community infrastructure

- Open a [community feedback issue](https://github.com/aiscihub-oss/community/issues/new?template=community-feedback.yml)
  or a focused pull request for fixes to the catalog, docs, or tooling.
- Read the [registry reference](registry/README.md) before editing entries.
  Use a maintainer-reviewed description and the repository's canonical name.
- Use a branch or fork; never push directly to `main`. For registry changes,
  run `python scripts/catalog.py refresh` and include the three generated
  files: `registry/metadata.json`, `PROJECTS.md`, and `docs/index.html`.
  For offline rendering, use `python scripts/catalog.py render`.
- Run `python -m unittest discover -s tests -v` and
  `python scripts/catalog.py check` before opening a pull request. Review all
  generated text and links. Do not add secrets or personal information.

## Update or remove a listing

Project maintainers can ask to update or remove their listing through a
community feedback issue or a pull request. A community maintainer verifies
the request using the repository's public maintainer context, without
requesting personal details. Removal affects the directory only, not the
original repository or its ownership.

Follow our [code of conduct](CODE_OF_CONDUCT.md) in all community interactions.
