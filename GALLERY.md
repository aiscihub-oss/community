# Project gallery

The visual gallery is generated from the same reviewed project registry
and public metadata snapshot as [PROJECTS.md](PROJECTS.md). There is no
separate project database, account system, or service. Search and category
filtering happen in the visitor's browser.

## Preview and regenerate

```bash
python scripts/catalog.py render
python -m unittest discover -s tests -v
python scripts/catalog.py check
```

Open `docs/index.html` directly in a browser. Alternatively, serve the
static directory locally:

```bash
python -m http.server --bind 127.0.0.1 --directory docs 8765
```

Visit `http://127.0.0.1:8765/`. The static page has no network dependencies.
Repository, license, release, and issue links take visitors to GitHub.

The template and renderer are in `scripts/gallery_template.html` and
`scripts/gallery.py`; styles and filters are in `docs/gallery.css` and
`docs/gallery.js`. Do not hand-edit the generated `docs/index.html`.

## Reviewed project images

The optional `cover` field in the registry points to an image already
reviewed and stored in `docs/assets/projects/`. Maintain the
[image credits](registry/gallery-assets.md). Covers are not required and
must not contain private or identifying information. The gallery does not
load images from external project websites or automatically fetch image
URLs submitted in issues.

## Publish on GitHub Pages

The gallery requires no new repository. After explicit deployment approval,
publish the reviewed gallery files to the existing
`aiscihub-oss/community` repository. In its Pages settings, choose
**Deploy from a branch**, select **main**, and choose **/docs**. The
`.nojekyll` file serves the static HTML directly.

The expected public URL is:

**https://aiscihub-oss.github.io/community/**

Verify the Pages deployment, the gallery links, and all four launch
project cards before publishing the organization profile update linking to the
gallery. The profile thumbnail gallery references reviewed copies of the
same assets in the community repository.

GitHub Pages is included for public repositories on GitHub Free. See
[GitHub Pages publishing-source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
No new hosting service or custom domain is needed.

## Ongoing review

The scheduled refresh generates `registry/metadata.json`, `PROJECTS.md`,
and `docs/index.html` together. The read-only workflow uploads exactly
those three files as its review artifact. Maintainers publish a reviewed
pull request; Pages then serves the updated gallery from `main/docs`.
Only reviewed registry entries appear on the gallery.
