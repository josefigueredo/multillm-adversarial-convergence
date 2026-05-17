/* deck-sync.js — wire the deck page into SlidesSync.
 *
 * Strategy: do NOT modify clean.js. Use the URL hash that clean.js
 * already listens for (`hashchange` triggers `show(N)`). Navigating
 * between views = hard location change.
 */
(() => {
  const VIEW_URLS = {
    glossary: "../glossary/glossary.html",
    demo: "../widgets/shell-demo.html",
    dashboard: "../widgets/dashboard-for-slide.html",
    deck: null, // already here
  };

  // Skip the very first broadcast on page load: respect explicit user
  // navigation (deep link, hash, or a freshly-opened tab from the index).
  // Subsequent state deltas drive normal cross-view + slide sync.
  let firstStateSeen = false;

  function go(state) {
    if (!state) return;
    if (!SlidesSync.following()) return;

    if (!firstStateSeen) {
      firstStateSeen = true;
      return;
    }

    // View switch (hard navigation)
    if (state.view && state.view !== "deck") {
      const url = VIEW_URLS[state.view];
      if (url && !location.pathname.endsWith(url.split("/").pop())) {
        location.href = url + (state.glossary_term ? `?term=${encodeURIComponent(state.glossary_term)}` : "");
        return;
      }
    }

    // Slide change within the deck
    const target = `#${state.slide || 1}`;
    if (location.hash !== target) location.hash = target;
  }

  SlidesSync.onState(go);

  document.addEventListener("slides:following", (e) => {
    if (e.detail && SlidesSync.state) go(SlidesSync.state);
  });
})();
