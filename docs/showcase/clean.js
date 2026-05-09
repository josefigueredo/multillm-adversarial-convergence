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

  // ── ScriptedTerminal — reusable per-slide terminal component ─────
  // Each .terminal element wraps a JSON script; arrow keys drive the
  // active slide's terminal when present.
  const TYPING_MS_PER_CHAR = 28;
  class ScriptedTerminal {
    constructor(root) {
      this.root = root;
      const dataEl = root.querySelector('script.terminal-script');
      this.script = dataEl ? JSON.parse(dataEl.textContent) : [];
      this.body  = root.querySelector('.terminal-body');
      this.curEl = root.querySelector('.terminal-cur');
      const totEl = root.querySelector('.terminal-total');
      if (totEl) totEl.textContent = this.script.length;
      this.position = 0;
      this.lines = [];
      this.isAnimating = false;
      this.snapNow = null;
      this.isPlaying = false;
      this.playTimer = null;
      this._refresh();
    }
    _refresh() { if (this.curEl) this.curEl.textContent = this.position; }
    _classFor(type) {
      return ({
        prompt:'prompt-line', typed:'prompt-line', output:'output-line',
        success:'success-line', error:'error-line',
        comment:'comment-line', heading:'heading-line',
      })[type] || 'output-line';
    }
    _appendLine(idx) {
      const step = this.script[idx];
      if (!step) return Promise.resolve();
      if (step.type === 'clear') { this._clear(); return Promise.resolve(); }
      const div = document.createElement('div');
      div.className = 'line ' + this._classFor(step.type);
      if (step.type === 'prompt' && step.text != null) {
        const p = document.createElement('span'); p.className = 'prompt-text'; p.textContent = step.prompt || '~ $ ';
        const t = document.createElement('span'); t.className = 'typed-text';
        div.appendChild(p); div.appendChild(t);
        this.body.appendChild(div); this.lines.push(div);
        this.body.scrollTop = this.body.scrollHeight;
        return this._animateTyping(t, step.text);
      }
      if (step.type === 'typed') {
        this.body.appendChild(div); this.lines.push(div);
        this.body.scrollTop = this.body.scrollHeight;
        return this._animateTyping(div, step.text);
      }
      if (step.type === 'prompt') {
        const p = document.createElement('span'); p.className = 'prompt-text'; p.textContent = step.prompt || '~ $ ';
        div.appendChild(p);
      } else {
        div.textContent = step.text ?? '';
      }
      this.body.appendChild(div); this.lines.push(div);
      this.body.scrollTop = this.body.scrollHeight;
      return Promise.resolve();
    }
    _animateTyping(target, text) {
      return new Promise((resolve) => {
        this.isAnimating = true;
        let i = 0, timer = null, resolved = false;
        const tick = () => {
          if (i < text.length) {
            target.textContent += text.charAt(i++);
            this.body.scrollTop = this.body.scrollHeight;
            timer = setTimeout(tick, TYPING_MS_PER_CHAR);
          } else { done(); }
        };
        const done = () => {
          if (resolved) return; resolved = true;
          clearTimeout(timer);
          this.isAnimating = false; this.snapNow = null; resolve();
        };
        this.snapNow = () => { target.textContent = text; this.body.scrollTop = this.body.scrollHeight; done(); };
        tick();
      });
    }
    _clear() { this.body.innerHTML = ''; this.lines = []; this.position = 0; this._refresh(); }
    async stepForward() {
      if (this.isAnimating && this.snapNow) { this.snapNow(); return; }
      if (this.position >= this.script.length) return;
      await this._appendLine(this.position);
      this.position++; this._refresh();
    }
    stepBackward() {
      if (this.isPlaying) this.stopPlay();
      if (this.isAnimating && this.snapNow) this.snapNow();
      if (this.position <= 0) return;
      this.position--;
      const last = this.lines.pop();
      if (last && last.parentNode) last.parentNode.removeChild(last);
      this._refresh();
    }
    async play() {
      if (this.isPlaying) return;
      this.isPlaying = true;
      while (this.isPlaying && this.position < this.script.length) {
        const idx = this.position;
        await this._appendLine(idx);
        this.position++; this._refresh();
        const delay = this.script[idx].delay ?? 350;
        if (!this.isPlaying) break;
        await new Promise((r) => { this.playTimer = setTimeout(r, delay); });
      }
      this.isPlaying = false;
    }
    stopPlay() {
      this.isPlaying = false; clearTimeout(this.playTimer);
      if (this.isAnimating && this.snapNow) this.snapNow();
    }
    reset() { this.stopPlay(); this._clear(); }
    async jumpEnd() {
      if (this.isAnimating && this.snapNow) this.snapNow();
      while (this.position < this.script.length) {
        await this._appendLine(this.position); this.position++;
      }
      this._refresh();
    }
  }
  const terminals = Array.from(document.querySelectorAll('.terminal')).map(el => new ScriptedTerminal(el));
  function activeTerminal() {
    const el = document.querySelector('.slide.active .terminal');
    return el ? terminals.find(t => t.root === el) : null;
  }
  // Reset terminal whenever its containing slide becomes active. We watch
  // the deck for class changes rather than monkey-patching show().
  const deckEl = document.querySelector('.deck');
  if (deckEl) {
    const obs = new MutationObserver(() => {
      const t = activeTerminal();
      if (t && t.position === 0 && t.lines.length === 0) return;
      if (t) t.reset();
    });
    obs.observe(deckEl, { subtree: true, attributes: true, attributeFilter: ['class'] });
  }

  // ── Keyboard ─────────────────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    // ignore if user is typing somewhere
    if (e.target.matches('input, textarea, [contenteditable]')) return;
    const t = activeTerminal();
    // Terminal-specific keys (only when active slide has a terminal)
    if (t) {
      switch (e.key) {
        case 'ArrowDown': e.preventDefault(); t.stepForward(); return;
        case 'ArrowUp':   e.preventDefault(); t.stepBackward(); return;
        case 'p': case 'P':
          e.preventDefault();
          if (t.isPlaying) t.stopPlay(); else t.play();
          return;
        case 'r': case 'R': e.preventDefault(); t.reset(); return;
      }
    }
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
        e.preventDefault();
        if (t) t.jumpEnd(); else last();
        break;
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
