/* deck-lang.js — floating ES/EN language switcher for the deck.
 *
 * Visual model: same pill chrome as follow-toggle.js (the
 * "Following presenter" widget), mounted top-left so they don't collide.
 *
 * Behavioural model: same as glossary's language switcher.
 *   - English is the source of truth (it lives in the HTML).
 *   - A dictionary (window.DECK_I18N[lang][key]) provides overrides.
 *   - Elements opted-in via data-i18n="<key>".
 *   - Missing keys fall back to the original English content silently.
 *
 * State resolution on first load:
 *   1. ?lang=<code> URL param (lets the index hand-off a preference)
 *   2. localStorage['deck-language']
 *   3. default: 'es'
 */
(() => {
  const STORAGE_KEY = "deck-language";

  // Keep the original (English) HTML for every translated element, so
  // switching back to EN restores it byte-for-byte. innerHTML preserves
  // inline <code>/<strong>/<em> inside translated strings if the dictionary
  // entry contains them.
  const originals = new WeakMap();

  function applyLang(next) {
    const dict = (window.DECK_I18N && window.DECK_I18N[next]) || {};
    document.documentElement.lang = next;
    try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}

    // Pass 1 — populate the originals cache for every annotated element
    // BEFORE we touch the DOM. Without this, a parent's mutation would
    // detach unsynced descendants and we'd cache the wrong "original."
    const all = Array.from(document.querySelectorAll("[data-i18n]"));
    all.forEach((el) => {
      if (!originals.has(el)) originals.set(el, el.innerHTML);
    });

    // Pass 2 — apply translations in DOM order, but with one rule for
    // nested annotations: if a PARENT has no translation of its own AND
    // contains annotated descendants, skip rewriting it. Otherwise the
    // parent's restore-to-original would clobber the child's Spanish.
    // Parents with their OWN translation still apply (they're expected to
    // include the inner markup in their dict value).
    all.forEach((el) => {
      const key = el.dataset.i18n;
      const hasOwnTranslation = dict[key] !== undefined;
      const hasAnnotatedDescendant = el.querySelector("[data-i18n]") !== null;
      if (!hasOwnTranslation && hasAnnotatedDescendant) return; // leave parent alone
      el.innerHTML = hasOwnTranslation ? dict[key] : originals.get(el);
    });

    document.querySelectorAll("#deck-lang [data-lang-btn]").forEach((b) => {
      b.classList.toggle("active", b.dataset.langBtn === next);
    });
  }

  function initialLang() {
    const param = new URLSearchParams(location.search).get("lang");
    if (param === "es" || param === "en") return param;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "es" || stored === "en") return stored;
    return "es";
  }

  function mount() {
    if (document.getElementById("deck-lang")) return;

    const style = document.createElement("style");
    style.textContent = `
      .deck-lang {
        position: fixed; top: 12px; left: 12px; z-index: 9999;
        font: 11px/1.4 'JetBrains Mono', ui-monospace, monospace;
        letter-spacing: .10em; text-transform: uppercase;
        background: rgba(13,17,23,.75); color: #b1bac4;
        border: 1px solid rgba(230,237,243,.22);
        border-radius: 999px;
        padding: 3px; display: inline-flex; align-items: center; gap: 2px;
        backdrop-filter: blur(10px);
        user-select: none;
      }
      .deck-lang button {
        font: inherit; background: transparent; color: inherit;
        border: 1px solid transparent; border-radius: 999px;
        padding: 4px 10px; cursor: pointer;
        transition: color 0.15s, border-color 0.15s, background 0.15s;
      }
      .deck-lang button:hover { color: #e6edf3; }
      .deck-lang button.active {
        border-color: #f5a524;
        color: #f5a524;
        background: rgba(245,165,36,0.10);
      }
    `;
    document.head.appendChild(style);

    const widget = document.createElement("div");
    widget.id = "deck-lang";
    widget.className = "deck-lang";
    widget.setAttribute("aria-label", "Deck language");
    widget.innerHTML = `
      <button type="button" data-lang-btn="es">ES</button>
      <button type="button" data-lang-btn="en">EN</button>
    `;
    document.body.appendChild(widget);

    widget.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-lang-btn]");
      if (btn) applyLang(btn.dataset.langBtn);
    });

    applyLang(initialLang());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
