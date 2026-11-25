# Project eligibility

AISciHub OSS is a curated directory of independently maintained open-source
software. It is not an automatic mirror of GitHub or a ranking of projects.

## Required

- **Public source.** A public, accessible, non-archived GitHub repository with
  meaningful software or a working software experiment, rather than an empty
  placeholder or an unmodified mirror. Repositories can belong to any GitHub
  user or organization.
- **Open-source license.** An explicit, nonempty license file using an
  [OSI-approved open-source license](https://opensource.org/licenses).
  The automated checker expects a GitHub-detected SPDX identifier from its
  [supported list](registry/projects.schema.json) matching the human-reviewed
  registry entry. For another OSI-approved license, propose a reviewed
  extension to the list; do not substitute an inaccurate identifier.
- **Useful README.** Explain the problem, what the software does, the main
  technology, how to set up and try it (or clearly describe current limits),
  and how developers can participate. Link the license. WIP projects are
  welcome if they set honest expectations.
- **Owner consent.** A repository maintainer submits the project or agrees
  to its listing. The original maintainers retain all ownership, release
  decisions, contributor access, and governance.
- **Community fit.** The listing is for useful open-source software, not a
  commercial promotion, paid-only product, course, competition, or credential.
  It follows the [code of conduct](CODE_OF_CONDUCT.md) and does not expose
  personal information or secrets in its submission.

## Strongly encouraged

- A short contribution guide, reproducible setup instructions, and tests.
- Clearly described issues, including a `good first issue` label when a
  task is suitable for a new contributor.
- Public release notes for projects that publish versions.

There is no minimum star count, user count, release count, contributor count,
school affiliation, or level of experience required.

## What is automated, and what is reviewed?

| Automated check | Human review |
| --- | --- |
| Strict registry schema and unique repository identity | Clear description, correct area, and owner consent |
| Public, enabled, non-archived repository | Meaningful software and suitability for the community |
| Nonempty README as exposed by GitHub | README is accurate, useful, and understandable |
| Nonempty license file and expected recognized SPDX ID | License text and open-source status are appropriate |
| Metadata snapshot matches the registry; catalog renders exactly | Diff, link destinations, and no personal/private information |

Both are required. License detection and a successful check do not constitute
a legal review, security audit, or endorsement. Maintainers may ask for
clarification, defer, decline, or remove listings that no longer meet these
standards, explaining the project-level reasons respectfully.
