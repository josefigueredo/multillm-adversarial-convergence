/* ─────────────────────────────────────────────────────────────────
   Clean deck runtime — no Marp, no Bespoke
   - Shows one slide at a time via .active class
   - Keyboard: ←/PgUp prev, →/PgDn/Space next, Home/End jump
   - Click anywhere on slide → next; Shift+click → prev
   - URL hash tracks current slide (#7)
   - Auto-scales every slide to fit the viewport (1280×720 reference)
   - Auto-injects a `<span class="page-num">N / 33</span>` per slide
   ───────────────────────────────────────────────────────────────── */
(() => {
  const slides = Array.from(document.querySelectorAll('.slide'));
  const total = slides.length;
  const indicator = document.getElementById('page-indicator');
  const prevBtn = document.getElementById('btn-prev');
  const nextBtn = document.getElementById('btn-next');
  const controls = document.querySelector('.deck-controls');

  // Inject per-slide page number (skip lead/no-page)
  slides.forEach((s, i) => {
    if (s.classList.contains('lead') || s.classList.contains('no-page')) return;
    const pn = document.createElement('span');
    pn.className = 'page-num';
    pn.textContent = `${i + 1} / ${total}`;
    s.appendChild(pn);
  });

  let current = 0;

  const clamp = (n) => Math.max(0, Math.min(total - 1, n));

  function show(idx, broadcast = true) {
    idx = clamp(idx);
    slides.forEach((s, i) => s.classList.toggle('active', i === idx));
    current = idx;
    if (indicator) indicator.textContent = `${idx + 1} / ${total}`;
    // sync URL hash without scrolling
    const newHash = `#${idx + 1}`;
    if (location.hash !== newHash) history.replaceState(null, '', newHash);
    // cross-tab sync: tell control.html (or another deck tab) where we are
    if (broadcast) {
      try { localStorage.setItem('deckCurrentSlide', String(idx + 1)); } catch (e) {}
    }
  }

  // ── Cross-tab sync: react when control.html navigates ──────────
  window.addEventListener('storage', (e) => {
    if (e.key !== 'deckCurrentSlide' || e.newValue == null) return;
    const n = parseInt(e.newValue, 10);
    if (!isNaN(n) && (n - 1) !== current) show(n - 1, false);
  });

  function next() { show(current + 1); }
  function prev() { show(current - 1); }
  function first() { show(0); }
  function last() { show(total - 1); }

  // ── Scaling: fit 1280×720 into viewport ──────────────────────────
  function rescale() {
    const sw = 1280, sh = 720;
    const scale = Math.min(window.innerWidth / sw, window.innerHeight / sh);
    document.documentElement.style.setProperty('--scale', scale.toFixed(4));
  }
  rescale();
  window.addEventListener('resize', rescale);

  // ── Keyboard ─────────────────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    // ignore if user is typing somewhere
    if (e.target.matches('input, textarea, [contenteditable]')) return;
    switch (e.key) {
      case 'ArrowRight':
      case 'PageDown':
      case ' ':
        e.preventDefault(); next(); break;
      case 'ArrowLeft':
      case 'PageUp':
        e.preventDefault(); prev(); break;
      case 'Home':
        e.preventDefault(); first(); break;
      case 'End':
        e.preventDefault(); last(); break;
      case 'f':
      case 'F':
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen?.();
        } else {
          document.exitFullscreen?.();
        }
        break;
    }
  });

  // ── Click on slide: next / shift+click: prev ─────────────────────
  document.querySelector('.deck')?.addEventListener('click', (e) => {
    // don't hijack clicks on links inside slides
    if (e.target.closest('a, button')) return;
    if (e.shiftKey) prev(); else next();
  });

  // ── Buttons ──────────────────────────────────────────────────────
  prevBtn?.addEventListener('click', (e) => { e.stopPropagation(); prev(); });
  nextBtn?.addEventListener('click', (e) => { e.stopPropagation(); next(); });

  // ── Reveal controls briefly on mouse move ────────────────────────
  let hideTimer = null;
  document.addEventListener('mousemove', () => {
    controls?.classList.add('visible');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => controls?.classList.remove('visible'), 1800);
  });

  // ── Hash navigation ──────────────────────────────────────────────
  function fromHash() {
    const m = location.hash.match(/^#(\d+)$/);
    if (m) {
      const n = parseInt(m[1], 10) - 1;
      if (n >= 0 && n < total) return n;
    }
    return 0;
  }
  window.addEventListener('hashchange', () => show(fromHash()));

  // ── Initial render ───────────────────────────────────────────────
  show(fromHash());
})();
