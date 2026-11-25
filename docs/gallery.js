"use strict";

// The gallery is fully readable without JavaScript. Filtering is local only.
document.addEventListener("DOMContentLoaded", () => {
  const filters = document.getElementById("gallery-filters");
  const search = document.getElementById("project-search");
  const area = document.getElementById("project-area");
  const clear = document.getElementById("clear-filters");
  const results = document.getElementById("project-results");
  const empty = document.getElementById("empty-state");
  const cards = Array.from(document.querySelectorAll(".project-card"));

  if (!filters || !search || !area || !clear || !results || !empty) return;
  filters.hidden = false;

  function applyFilters() {
    const query = search.value.trim().toLocaleLowerCase();
    const words = query.split(/\s+/).filter(Boolean);
    const category = area.value;
    let visible = 0;

    for (const card of cards) {
      const text = (card.dataset.search || "").toLocaleLowerCase();
      const matchesSearch = words.every((word) => text.includes(word));
      const matchesArea = !category || card.dataset.category === category;
      const matches = matchesSearch && matchesArea;
      card.hidden = !matches;
      if (matches) visible += 1;
    }

    results.textContent =
      visible === cards.length
        ? `${visible} ${visible === 1 ? "project" : "projects"}`
        : `Showing ${visible} of ${cards.length} projects`;
    empty.hidden = visible !== 0;
    clear.disabled = !query && !category;
  }

  search.addEventListener("input", applyFilters);
  area.addEventListener("change", applyFilters);
  clear.addEventListener("click", () => {
    search.value = "";
    area.value = "";
    applyFilters();
    search.focus();
  });
  applyFilters();
});
