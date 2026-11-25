"""Render a static project gallery from the reviewed catalog data."""

from html import escape
from pathlib import Path
from string import Template
from urllib.parse import quote, urlencode


TEMPLATE = Path(__file__).with_name("gallery_template.html")


def html(value):
    """External metadata and approved text are still data, never markup."""
    return escape(str(value), quote=True)


def project_card(project, metadata, categories):
    repo = project["repository"]
    base = f"https://github.com/{repo}"
    name = html(project["name"])
    category = html(project["category"])
    category_title = html(categories[project["category"]])
    summary = html(project["summary"])
    language = html(metadata["language"] or "Language not detected")
    license_url = html(f"{base}/blob/HEAD/{quote(metadata['license_path'], safe='/')}")
    license_name = html(metadata["license"])

    if project.get("cover"):
        cover = project["cover"]
        cover_html = (
            f'<img src="assets/projects/{html(cover["image"])}" '
            f'alt="{html(cover["alt"])}" loading="lazy" decoding="async">'
        )
    else:
        cover_html = (
            '<div class="cover-fallback" aria-hidden="true">'
            '<span class="cover-symbol">&lt;/&gt;</span>'
            f'<span>{name}</span>'
            '</div>'
        )

    release = metadata["latest_release"]
    if release:
        tag = html(release["tag"])
        release_url = html(f"{base}/releases/tag/{quote(release['tag'], safe='')}")
        release_html = f'<a href="{release_url}">{tag}</a>'
    else:
        release_html = '<span class="release-empty">No stable release yet</span>'

    if metadata["issues_enabled"]:
        query = urlencode({"q": 'is:issue is:open label:"good first issue"'})
        issue_url = html(f"{base}/issues?{query}")
        issue_label = "Good first issues" if metadata["good_first_issues"] else "Browse first issues"
        issue_html = f'<a class="text-link" href="{issue_url}">{issue_label}</a>'
    else:
        issue_html = '<span class="muted small">Issues disabled</span>'

    search_text = html(
        " ".join(
            [
                project["name"],
                project["summary"],
                repo,
                categories[project["category"]],
                metadata["language"] or "",
                metadata["license"],
            ]
        )
    )
    return f"""
      <article class="project-card" data-category="{category}" data-search="{search_text}">
        <a class="project-cover category-{category}" href="{html(base)}" aria-label="Open {name} on GitHub">
          {cover_html}
        </a>
        <div class="project-body">
          <p class="project-category category-{category}">{category_title}</p>
          <h3>{name}</h3>
          <p class="project-summary">{summary}</p>
          <div class="project-tags" aria-label="Project metadata">
            <span class="tag">{language}</span>
            <a class="tag" href="{license_url}" title="View the license">{license_name}</a>
          </div>
          <p class="project-release"><span>Latest GitHub release</span>{release_html}</p>
          <div class="project-actions">
            <a class="button button-project" href="{html(base)}">View repository</a>
            {issue_html}
          </div>
        </div>
      </article>""".strip("\n")


def render_gallery(registry, snapshot, categories):
    """Deterministic HTML with no remote image fetches or runtime API calls."""
    metadata = {item["repository"]: item for item in snapshot["projects"]}
    projects = registry["projects"]
    active_categories = {project["category"] for project in projects}
    options = [
        f'          <option value="{html(key)}">{html(title)}</option>'
        for key, title in categories.items()
        if key in active_categories
    ]
    # Registry order is a reviewed editorial choice, not a popularity ranking.
    cards = [
        project_card(project, metadata[project["repository"]], categories)
        for project in projects
    ]
    count = len(projects)
    plural = "project" if count == 1 else "projects"
    template = Template(TEMPLATE.read_text(encoding="utf-8"))
    return template.substitute(
        project_count=count,
        count_label=f"{count} {plural}",
        project_plural=plural,
        gallery_columns="four" if count >= 4 else "three",
        checked_on=html(snapshot["checked_on"]),
        category_options="\n".join(options),
        project_cards="\n".join(cards),
        empty_hidden="hidden" if count else "",
    )
