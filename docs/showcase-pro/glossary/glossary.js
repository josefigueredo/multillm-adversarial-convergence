(function () {
  const terms = Array.isArray(window.GLOSSARY_TERMS) ? window.GLOSSARY_TERMS : [];
  const i18n = window.GLOSSARY_I18N || {};
  const searchInput = document.getElementById("search");
  const clearButton = document.getElementById("clear-search");
  const filtersEl = document.getElementById("filters");
  const listEl = document.getElementById("term-list");
  const detailEl = document.getElementById("detail-card");
  const resultCountEl = document.getElementById("result-count");
  const languageButtons = Array.from(document.querySelectorAll("[data-language]"));

  let activeCategory = "All";
  let filtered = [];
  let activeIndex = 0;
  let language = localStorage.getItem("glossary-language") || "es";

  const enUi = {
    searchLabel: "Search concept",
    clear: "Clear",
    staticData: "offline · static data",
    ready: "READY",
    emptyTitle: "Type a term or pick one from the list.",
    emptyBody: "The card will show a plain definition, business analogy, technical analogy, why it matters, and how the concept maps to this project.",
    hintFocus: "focus search",
    hintMove: "move",
    hintOpen: "open selected",
    hintClear: "clear",
    noMatch: "NO MATCH",
    noConcept: "No concept selected.",
    tryTerms: "Try terms like harness, agent, judge, context, sandbox, resume, or citation coverage.",
    noResults: "No matching terms. Try a broader word.",
    concept: "CONCEPT",
    plain: "Plain Definition",
    business: "Business Analogy",
    technical: "Technical Analogy",
    matters: "Why It Matters",
    project: "In This Project",
    related: "Related Terms",
    termsSingular: "term",
    termsPlural: "terms",
    placeholder: "Try: harness, judge, context window, sandbox..."
  };

  function normalize(value) {
    return String(value || "").toLowerCase().trim();
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function t(key) {
    return i18n[language]?.ui?.[key] || enUi[key] || key;
  }

  function localizedCategory(category) {
    if (language === "en") return category;
    return i18n[language]?.filters?.[category] || category;
  }

  function localized(item) {
    const translated = language === "en" ? {} : (i18n[language]?.terms?.[item.term] || {});
    return {
      ...item,
      ...translated,
      aliases: translated.aliases || item.aliases || [],
      related: translated.related || item.related || [],
      category: item.category,
      categoryLabel: localizedCategory(item.category)
    };
  }

  function searchableText(item) {
    const translated = localized(item);
    return [
      item.term,
      translated.term,
      item.category,
      translated.categoryLabel,
      item.plain,
      translated.plain,
      item.business,
      translated.business,
      item.technical,
      translated.technical,
      item.matters,
      translated.matters,
      item.project,
      translated.project,
      ...(item.aliases || []),
      ...(translated.aliases || []),
      ...(item.related || [])
    ].join(" ");
  }

  function categories() {
    return ["All", "None", ...Array.from(new Set(terms.map((item) => item.category))).sort()];
  }

  function applyStaticText() {
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.getAttribute("data-i18n"));
    });
    searchInput.placeholder = t("placeholder");
    clearButton.setAttribute("aria-label", t("clear"));
    languageButtons.forEach((button) => {
      button.classList.toggle("active", button.getAttribute("data-language") === language);
    });
  }

  function renderFilters() {
    filtersEl.innerHTML = "";
    categories().forEach((category) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `filter${category === activeCategory ? " active" : ""}`;
      button.textContent = localizedCategory(category);
      button.addEventListener("click", () => {
        activeCategory = category;
        activeIndex = 0;
        render();
      });
      filtersEl.appendChild(button);
    });
  }

  function filterTerms() {
    const query = normalize(searchInput.value);
    filtered = terms.filter((item) => {
      if (activeCategory === "None") return false;
      const categoryMatch = activeCategory === "All" || item.category === activeCategory;
      const queryMatch = !query || normalize(searchableText(item)).includes(query);
      return categoryMatch && queryMatch;
    });
    if (activeIndex >= filtered.length) activeIndex = Math.max(0, filtered.length - 1);
  }

  function renderList() {
    listEl.innerHTML = "";
    const label = filtered.length === 1 ? t("termsSingular") : t("termsPlural");
    resultCountEl.textContent = `${filtered.length} ${label}`;

    if (!filtered.length) {
      const empty = document.createElement("p");
      empty.className = "no-results";
      empty.textContent = t("noResults");
      listEl.appendChild(empty);
      renderEmpty();
      return;
    }

    filtered.forEach((item, index) => {
      const displayItem = localized(item);
      const button = document.createElement("button");
      button.type = "button";
      button.className = `term-button${index === activeIndex ? " active" : ""}`;
      button.innerHTML = `
        <span>${escapeHtml(displayItem.categoryLabel)}</span>
        <strong>${escapeHtml(displayItem.term)}</strong>
        <p>${escapeHtml(displayItem.plain)}</p>
      `;
      button.addEventListener("click", () => {
        activeIndex = index;
        renderList();
        renderDetail(item);
      });
      listEl.appendChild(button);
    });
  }

  function renderEmpty() {
    detailEl.innerHTML = `
      <div class="empty-state">
        <span class="empty-kicker">${escapeHtml(t("noMatch"))}</span>
        <h1>${escapeHtml(t("noConcept"))}</h1>
        <p>${escapeHtml(t("tryTerms"))}</p>
      </div>
    `;
  }

  function renderDetail(item) {
    const displayItem = localized(item);
    const aliases = (displayItem.aliases || []).map(escapeHtml).join(" · ");
    const related = (displayItem.related || []).map((term) => `
      <button type="button" data-related="${escapeHtml(term)}">${escapeHtml(term)}</button>
    `).join("");

    detailEl.innerHTML = `
      <div class="detail-header">
        <div>
          <span class="detail-kicker">${escapeHtml(t("concept"))}</span>
          <h1>${escapeHtml(displayItem.term)}</h1>
          <p class="aliases">${aliases}</p>
        </div>
        <span class="category-chip">${escapeHtml(displayItem.categoryLabel)}</span>
      </div>

      <div class="detail-grid">
        <section class="concept-block wide">
          <h2>${escapeHtml(t("plain"))}</h2>
          <p>${escapeHtml(displayItem.plain)}</p>
        </section>
        <section class="concept-block">
          <h2>${escapeHtml(t("business"))}</h2>
          <p>${escapeHtml(displayItem.business)}</p>
        </section>
        <section class="concept-block">
          <h2>${escapeHtml(t("technical"))}</h2>
          <p>${escapeHtml(displayItem.technical)}</p>
        </section>
        <section class="concept-block">
          <h2>${escapeHtml(t("matters"))}</h2>
          <p>${escapeHtml(displayItem.matters)}</p>
        </section>
        <section class="concept-block">
          <h2>${escapeHtml(t("project"))}</h2>
          <p>${escapeHtml(displayItem.project)}</p>
        </section>
        <section class="concept-block wide">
          <h2>${escapeHtml(t("related"))}</h2>
          <div class="related">${related}</div>
        </section>
      </div>
    `;

    detailEl.querySelectorAll("[data-related]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.getAttribute("data-related");
        searchInput.value = target;
        activeCategory = "All";
        activeIndex = 0;
        render();
        searchInput.focus();
      });
    });
  }

  function render() {
    applyStaticText();
    renderFilters();
    filterTerms();
    renderList();
    if (filtered.length) renderDetail(filtered[activeIndex]);
  }

  function moveActive(delta) {
    if (!filtered.length) return;
    activeIndex = Math.max(0, Math.min(filtered.length - 1, activeIndex + delta));
    renderList();
    renderDetail(filtered[activeIndex]);
    const activeButton = listEl.querySelector(".term-button.active");
    if (activeButton) activeButton.scrollIntoView({ block: "nearest" });
  }

  searchInput.addEventListener("input", () => {
    activeIndex = 0;
    render();
  });

  clearButton.addEventListener("click", () => {
    searchInput.value = "";
    activeCategory = "All";
    activeIndex = 0;
    render();
    searchInput.focus();
  });

  languageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      language = button.getAttribute("data-language") || "es";
      localStorage.setItem("glossary-language", language);
      render();
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && document.activeElement !== searchInput) {
      event.preventDefault();
      searchInput.focus();
      return;
    }

    if (event.key === "Escape") {
      searchInput.value = "";
      activeCategory = "All";
      activeIndex = 0;
      render();
      searchInput.focus();
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActive(1);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActive(-1);
      return;
    }

    if (event.key === "Enter" && filtered[activeIndex]) {
      renderDetail(filtered[activeIndex]);
    }
  });

  render();
})();
