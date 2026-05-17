/* slides-template-pro — sync adapter
 * ─────────────────────────────────────────────────────────────────
 * One file loaded by every page (deck, glossary, widgets, presenter)
 * that wants to participate in remote-controlled playback.
 *
 *   <script src="/docs/showcase/sync/sync.js" data-role="viewer"></script>
 *   <script src="/docs/showcase/sync/sync.js" data-role="presenter"></script>
 *
 * Public surface (under window.SlidesSync):
 *   - state            current state object (read-only)
 *   - onState(fn)      subscribe to state changes; returns unsubscribe
 *   - control(patch)   presenter-only: POST a state patch
 *   - following        viewer-only: bool, persisted in localStorage
 *   - setFollowing(b)  toggle "follow presenter"
 *
 * The adapter does NOT navigate or render anything itself. Each page
 * wires its own reaction to state changes via onState().
 * ─────────────────────────────────────────────────────────────────*/
(() => {
  const scriptTag = document.currentScript;
  const role = scriptTag?.dataset.role || "viewer";

  const STORAGE_FOLLOWING = "slides.following";
  const STORAGE_API_KEY = "slides.apiKey";

  const listeners = new Set();
  let state = null;
  let ws = null;
  let reconnectAttempt = 0;
  let runtime = null;

  function emit(next) {
    state = next;
    for (const fn of listeners) {
      try { fn(state); } catch (err) { console.error("[sync] listener error", err); }
    }
  }

  async function loadRuntime() {
    // The local dev server serves /api/runtime-config. In production, the
    // page itself injects window.SLIDES_RUNTIME via a small inline script
    // (or a static config.js) so we don't depend on a same-origin API.
    if (window.SLIDES_RUNTIME) return window.SLIDES_RUNTIME;
    try {
      const r = await fetch("/api/runtime-config", { cache: "no-store" });
      if (r.ok) return await r.json();
    } catch (_) { /* fall through */ }
    console.warn("[sync] no runtime config found; sync disabled");
    return null;
  }

  function backoff() {
    // 0.5s, 1s, 2s, 4s, 8s — cap at 8s
    const ms = Math.min(500 * 2 ** reconnectAttempt, 8000);
    reconnectAttempt += 1;
    return ms;
  }

  function connect() {
    if (!runtime?.wsUrl) return;
    ws = new WebSocket(runtime.wsUrl);
    ws.addEventListener("open", () => {
      reconnectAttempt = 0;
      console.info("[sync] connected to", runtime.wsUrl);
    });
    ws.addEventListener("message", (e) => {
      try {
        const next = JSON.parse(e.data);
        if (state && typeof next.version === "number" && next.version < state.version) {
          return; // ignore out-of-order
        }
        emit(next);
      } catch (err) {
        console.error("[sync] bad message", err);
      }
    });
    ws.addEventListener("close", () => {
      ws = null;
      const delay = backoff();
      console.warn(`[sync] disconnected, retrying in ${delay}ms`);
      setTimeout(connect, delay);
    });
    ws.addEventListener("error", () => { /* close fires next */ });
  }

  function getApiKey() {
    return runtime?.apiKey || localStorage.getItem(STORAGE_API_KEY) || "";
  }

  function setApiKey(key) {
    localStorage.setItem(STORAGE_API_KEY, key || "");
  }

  async function control(patch) {
    if (role !== "presenter") {
      console.warn("[sync] control() called from non-presenter page");
      return null;
    }
    if (!runtime?.controlUrl) return null;
    const res = await fetch(runtime.controlUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": getApiKey(),
      },
      body: JSON.stringify(patch),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      console.error("[sync] control failed", res.status, body);
      return null;
    }
    const next = await res.json();
    emit(next); // local optimistic update; broadcast will arrive too
    return next;
  }

  function following() {
    const stored = localStorage.getItem(STORAGE_FOLLOWING);
    return stored === null ? true : stored === "1";
  }

  function setFollowing(value) {
    localStorage.setItem(STORAGE_FOLLOWING, value ? "1" : "0");
    document.dispatchEvent(new CustomEvent("slides:following", { detail: value }));
  }

  function onState(fn) {
    listeners.add(fn);
    if (state) try { fn(state); } catch (_) {}
    return () => listeners.delete(fn);
  }

  window.SlidesSync = {
    get state() { return state; },
    get role() { return role; },
    get runtime() { return runtime; },
    onState,
    control,
    following,
    setFollowing,
    setApiKey,
  };

  loadRuntime().then((cfg) => {
    runtime = cfg;
    if (cfg) connect();
  });
})();
