# AISciHub OSS · community

A free, youth-led, cross-school community for open-source software.
This repository is the home of the project catalog, submission process,
and community standards. Listed projects stay with their original developers.

**[Explore the project catalog](PROJECTS.md)** ·
**[Submission process](CONTRIBUTING.md#submit-a-project)** ·
**[Contribute](CONTRIBUTING.md)**

> **Initial catalog preview:** The seed projects are listed. New project
> submissions will open after the maintainer review rules are activated.

## Start here

| I want to… | Go to |
| --- | --- |
| Find software or a first contribution | [Project catalog](PROJECTS.md) |
| List a project from any public GitHub account | [Submission guide](CONTRIBUTING.md#submit-a-project) |
| Understand the quality bar | [Project eligibility](PROJECT_ELIGIBILITY.md) |
| Understand community expectations | [Code of conduct](CODE_OF_CONDUCT.md) |
| Maintain the community | [Maintainer responsibilities](MAINTAINERS.md) |
| Work on the registry and automation | [Registry reference](registry/README.md) |

We welcome practical software at any stage of development when it is documented
well enough for another developer to understand and contribute. There are no
courses, competitions, certificates, fees, or required school affiliations.
You do not need to join the GitHub organization or transfer your repository.

## How the catalog works

1. A developer proposes a project through a public GitHub Issue Form.
2. Community maintainers verify eligibility and the project owners' consent.
3. A reviewed pull request adds or updates the project in
   [the YAML registry](registry/projects.yml).
4. Read-only GitHub Actions validate the registry and public repositories.
   A human maintainer approves the pull request before it is merged.
5. A separate scheduled workflow generates an updated metadata snapshot and
   Markdown catalog from the reviewed registry on `main`. Maintainers review
   and publish the generated files through a pull request.

Issues cannot add entries to the registry. The approved registry on `main`
is the only source of catalog membership, and no workflow pushes or merges
changes. The catalog is a dated, reviewed snapshot rather than a live feed.

## Local development

Use Python 3.12. All tests and the offline catalog check run without network
access after installing dependencies.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r requirements.txt

python -m unittest discover -s tests -v
python scripts/catalog.py check
```

| Command | Purpose |
| --- | --- |
| `python scripts/catalog.py check` | Offline schema, membership, and generated-file consistency checks |
| `python scripts/catalog.py validate` | Live checks of each public repository's identity, availability, README, and license |
| `python scripts/catalog.py refresh` | Fetch public metadata and regenerate `registry/metadata.json` and `PROJECTS.md` |
| `python scripts/catalog.py render` | Rebuild just the Markdown from the checked metadata snapshot, offline |

The live commands use the public GitHub REST API. They work anonymously for
small registries. GitHub Actions uses its built-in, read-only `GITHUB_TOKEN`
where supported and retries a scope-denied public request anonymously.
No additional credentials are needed; rate-limit errors fail the check.
Nothing is cloned, installed, or executed from listed repositories.

## Project information only

GitHub issues and pull requests are public. Please don't include real names,
ages, school names, contact details, private documents, secrets, or other
personal information in submissions. We don't maintain a student roster or
ask for identity verification. The catalog stores only project-level
information, not contributor profiles or issue bodies.

The infrastructure is available under the [MIT license](LICENSE).
Individual projects retain their own licenses and governance.
