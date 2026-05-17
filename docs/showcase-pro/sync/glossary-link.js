/* glossary-link.js — click handler for inline glossary terms.
 *
 * Behavior depends on the role of the page that loaded sync.js:
 *   - presenter: clicks broadcast { view: "glossary", glossary_term }
 *   - viewer:    clicks open the glossary in a new tab with ?term=...
 *
 * No modification of clean.js needed; we attach at the document level
 * and stop the deck's own click handler with stopPropagation so it
 * doesn't advance the slide.
 */
(() => {
  document.addEventListener("click", (e) => {
    const el = e.target.closest(".g-term");
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();

    const term = el.dataset.term;
    if (!term) return;

    if (window.SlidesSync?.role === "presenter") {
      SlidesSync.control({ view: "glossary", glossary_term: term });
    } else {
      window.open(`../glossary/glossary.html?term=${encodeURIComponent(term)}`, "_blank");
    }
  });
})();
