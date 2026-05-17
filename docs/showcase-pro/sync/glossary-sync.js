/* glossary-sync.js — wire the glossary page into SlidesSync.
 *
 * Two jobs:
 *   1. If a ?term=... param is in the URL on load, focus that term.
 *   2. React to broadcast state changes by simulating a search.
 *
 * The glossary's own runtime is untouched — we drive it through the
 * existing search input and dispatch an 'input' event so its listeners
 * fire naturally.
 */
(() => {
  function focusTerm(term) {
    const input = document.getElementById("search");
    if (!input || !term) return;
    if (input.value === term) return;
    input.value = term;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // Skip the very first broadcast on page load — the user navigated HERE,
  // so don't yank them to a different view just because state.view differs.
  // Term sync is still useful on initial load (deep-link a specific term).
  let firstStateSeen = false;

  function go(state) {
    if (!state) return;
    if (!SlidesSync.following()) return;

    if (!firstStateSeen) {
      firstStateSeen = true;
      focusTerm(state.glossary_term);
      return;
    }

    if (state.view && state.view !== "glossary") {
      // Presenter switched away from glossary — navigate to the appropriate view.
      const map = {
        deck: "../deck/deck.html",
        demo: "../widgets/shell-demo.html",
        dashboard: "../widgets/dashboard-for-slide.html",
      };
      const url = map[state.view];
      if (url) {
        location.href = state.slide ? `${url}#${state.slide}` : url;
        return;
      }
    }

    focusTerm(state.glossary_term);
  }

  // Initial term from query string (so deep-linking via plain HTTP works too)
  const params = new URLSearchParams(location.search);
  const initialTerm = params.get("term");
  if (initialTerm) {
    // Wait for the glossary's own boot to finish before driving the input.
    requestAnimationFrame(() => focusTerm(initialTerm));
  }

  SlidesSync.onState(go);
  document.addEventListener("slides:following", (e) => {
    if (e.detail && SlidesSync.state) go(SlidesSync.state);
  });
})();
