/* follow-toggle.js — inject a small "Following presenter" widget.
 *
 * Drop on any viewer page; the page wires its own reaction to the
 * `slides:following` event (already dispatched by sync.js).
 */
(() => {
  const css = `
    .slides-follow {
      position: fixed; top: 12px; right: 12px; z-index: 9999;
      font: 11px/1.4 'JetBrains Mono', ui-monospace, monospace;
      letter-spacing: .12em; text-transform: uppercase;
      background: rgba(13,17,23,.75); color: #b1bac4;
      border: 1px solid rgba(230,237,243,.22);
      padding: 6px 10px 6px 8px; border-radius: 999px;
      display: inline-flex; align-items: center; gap: 8px;
      backdrop-filter: blur(10px); cursor: pointer; user-select: none;
    }
    .slides-follow .dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: #7ee787; box-shadow: 0 0 8px #7ee78766;
    }
    .slides-follow[data-following="false"] .dot { background: #7d8590; box-shadow: none; }
    .slides-follow[data-following="false"] { color: #7d8590; }
  `;

  function mount() {
    if (document.getElementById("slides-follow")) return;
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);

    const btn = document.createElement("button");
    btn.id = "slides-follow";
    btn.className = "slides-follow";
    btn.type = "button";
    btn.dataset.following = String(SlidesSync.following());
    btn.innerHTML = `<span class="dot"></span><span class="label"></span>`;
    document.body.appendChild(btn);

    function render() {
      const on = SlidesSync.following();
      btn.dataset.following = String(on);
      btn.querySelector(".label").textContent = on ? "following presenter" : "free roam";
    }
    render();

    btn.addEventListener("click", () => {
      SlidesSync.setFollowing(!SlidesSync.following());
      render();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
