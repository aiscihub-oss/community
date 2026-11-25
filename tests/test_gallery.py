"""Offline gallery tests: rendering, local assets, and approved membership."""

import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit

from scripts import catalog
from scripts.gallery import render_gallery
from test_catalog import FakeGitHub, project, registry


class GalleryParser(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.cards = []
        self.links = []
        self.resources = []
        self.images = []
        self.scripts = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "project-card" in attrs.get("class", "").split():
            self.cards.append(attrs)
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "img":
            self.images.append(attrs)
        if tag in {"img", "script"} and "src" in attrs:
            self.resources.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.resources.append(attrs["href"])


class GalleryTests(unittest.TestCase):
    def render(self, *projects):
        data = registry(*projects)
        snapshot = catalog.collect_metadata(data, FakeGitHub(*projects), "2026-11-25")
        return render_gallery(data, snapshot, catalog.CATEGORIES)

    def test_gallery_renders_actual_approved_projects_and_release_links(self):
        a = project("independent/tool", 100, name="Tool")
        b = project("cross-school/civic", 200, name="Civic", category="civic-tech")
        document = self.render(a, b)
        parsed = GalleryParser(document)
        self.assertEqual(len(parsed.cards), 2)
        self.assertEqual([card["data-category"] for card in parsed.cards], ["developer-tools", "civic-tech"])
        self.assertIn("https://github.com/independent/tool", parsed.links)
        self.assertIn("https://github.com/cross-school/civic", parsed.links)
        self.assertIn("https://github.com/independent/tool/releases/tag/v1.2.3", parsed.links)
        self.assertTrue(any(link.startswith("https://github.com/independent/tool/issues?q=") for link in parsed.links))
        self.assertIn("2 projects", document)
        self.assertIn("2026-11-25", document)
        self.assertEqual(document, self.render(a, b))

    def test_cover_and_fallback_are_rendered_without_remote_images(self):
        p = project(cover={"image": "example.png", "alt": "Public preview"})
        document = self.render(p, project("another/other", 56789))
        parsed = GalleryParser(document)
        self.assertTrue(any(img.get("src") == "assets/projects/example.png" and img.get("alt") == "Public preview" for img in parsed.images))
        self.assertIn('class="cover-fallback"', document)
        self.assertTrue(all(not urlsplit(src).scheme and not src.startswith("//") for src in parsed.resources))

    def test_untrusted_text_is_escaped_as_html_and_attributes(self):
        p = project(
            name='A <b>tool</b> "quoted"',
            summary='Text with <em>markup</em> & an external URL https://example.test.',
            cover={"image": "example.png", "alt": 'A "quoted" <preview>'},
        )
        document = self.render(p)
        parsed = GalleryParser(document)
        self.assertIn("A &lt;b&gt;tool&lt;/b&gt; &quot;quoted&quot;", document)
        self.assertNotIn("<em>markup</em>", document)
        self.assertEqual(len(parsed.cards), 1)
        self.assertEqual(len(parsed.scripts), 1)
        self.assertTrue(all(urlsplit(link).netloc in {"", "github.com"} for link in parsed.links))
        self.assertIn('A &quot;quoted&quot; &lt;preview&gt;', document)

    def test_empty_gallery_and_missing_optional_metadata(self):
        empty = self.render()
        self.assertEqual(len(GalleryParser(empty).cards), 0)
        self.assertIn("0 projects", empty)
        self.assertIn('id="empty-state"', empty)
        p = project()
        api = FakeGitHub(p)
        api.responses[(p["repository"], "")].update(language=None, has_issues=False)
        api.responses[(p["repository"], "/releases/latest")] = None
        data = registry(p)
        snapshot = catalog.collect_metadata(data, api, "2026-11-25")
        document = render_gallery(data, snapshot, catalog.CATEGORIES)
        self.assertIn("Language not detected", document)
        self.assertIn("No stable release yet", document)
        self.assertIn("Issues disabled", document)
        self.assertNotIn("Good first issues</a>", document)

    def test_four_project_gallery_uses_wide_grid_and_preserves_registry_order(self):
        projects = [
            project("owner/one", 1, name="One"),
            project("owner/two", 2, name="Two"),
            project("owner/three", 3, name="Three", category="scientific-computing"),
            project("owner/four", 4, name="Four", category="scientific-computing"),
        ]
        document = self.render(*projects)
        parsed = GalleryParser(document)
        self.assertEqual(len(parsed.cards), 4)
        self.assertIn('id="project-grid" data-columns="four"', document)
        self.assertEqual(
            [entry["data-category"] for entry in parsed.cards],
            ["developer-tools", "developer-tools", "scientific-computing", "scientific-computing"],
        )
        self.assertLess(document.index("<h3>Three</h3>"), document.index("<h3>Four</h3>"))

    def test_shipped_gallery_resources_exist_and_match_registry(self):
        data = catalog.load_registry()
        document = (catalog.ROOT / "docs/index.html").read_text(encoding="utf-8")
        parsed = GalleryParser(document)
        self.assertEqual(len(parsed.cards), len(data["projects"]))
        docs = catalog.ROOT / "docs"
        for resource in parsed.resources:
            with self.subTest(resource=resource):
                self.assertTrue((docs / resource).resolve().is_relative_to(docs.resolve()))
                self.assertTrue((docs / resource).is_file())
        self.assertTrue((docs / ".nojekyll").is_file())


if __name__ == "__main__":
    unittest.main()
