---
marp: true
theme: default
paginate: true
size: 16:9
backgroundColor: '#0a0c10'
header: 'MULTI-LLM ADVERSARIAL CONVERGENCE'
footer: 'github.com/josefigueredo/multillm-adversarial-convergence'
style: |
  /* ─────────────────────────────────────────────────────────────────
     CRT / PHOSPHOR — pro deck system
     - One palette: deep terminal black + amber phosphor + cool cyan
     - One typography pair: Geist (display) + JetBrains Mono (system)
     - Frosted glass panels so the pixelated loop bleeds through every slide
     - Video-bg mode reserved for cover, dividers, and closer
     ───────────────────────────────────────────────────────────────── */
  @import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

  :root {
    --bg-deep:        #0a0c10;
    --bg-panel:       rgba(13, 17, 23, 0.78);
    --bg-panel-soft:  rgba(13, 17, 23, 0.55);
    --bg-panel-vbg:   rgba(10, 12, 16, 0.42);
    --ink:            #e6edf3;
    --ink-soft:       #b1bac4;
    --ink-mute:       #7d8590;
    --hairline:       rgba(230, 237, 243, 0.10);
    --hairline-2:     rgba(230, 237, 243, 0.22);
    --phosphor:       #f5a524;  /* amber — primary accent */
    --phosphor-cool:  #22d3ee;  /* cyan — links, KEEP, pull quotes */
    --phosphor-green: #7ee787;  /* code on dark — CRT green */
    --phosphor-warn:  #ff7b72;  /* errors, denials, DISCARD */
  }

  /* ── BASE SECTION ─────────────────────────────────────────────── */
  section {
    font-family: 'Geist', system-ui, -apple-system, sans-serif;
    font-size: 24px;
    line-height: 1.55;
    color: var(--ink);
    padding: 56px 72px 64px;
    letter-spacing: -0.005em;
    font-feature-settings: 'ss01', 'ss03', 'cv11';
    /* layered bg: scanlines + phosphor glow + dark panel */
    background-color: var(--bg-panel) !important;
    background-image:
      repeating-linear-gradient(0deg, rgba(0,0,0,0.14) 0 1px, transparent 1px 3px),
      radial-gradient(circle at 100% 0%, rgba(245,165,36,0.08), transparent 55%),
      radial-gradient(circle at 0% 100%, rgba(34,211,238,0.05), transparent 50%);
    backdrop-filter: blur(24px) saturate(1.35);
    -webkit-backdrop-filter: blur(24px) saturate(1.35);
  }

  /* ── MARP ADVANCED-BG SECTIONS (used by `bg right:N%` directive) ─
     Marp emits 3 <section>s per slide that uses bg-right:
       1. "background"  — full-width, holds the image <figure>; painted first (bottom)
       2. content        — 48% wide, painted second (above bg, contains text)
       3. "pseudo"       — full-width, painted last (top); only carries header/footer
     The pseudo section MUST be transparent or it covers content. The
     background section keeps the glass so the slide reads as a unified
     panel with the image floating on top of it. */
  section[data-marpit-advanced-background="pseudo"] {
    background-color: transparent !important;
    background-image: none !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
  }
  /* Frame the screenshot image rendered by `bg right` so it doesn't
     sit naked against the video — match the box-shadow used for inline
     screenshots elsewhere in the deck. */
  section[data-marpit-advanced-background="background"] figure {
    box-shadow:
      0 16px 60px rgba(0, 0, 0, 0.6),
      inset 0 0 0 1px rgba(230, 237, 243, 0.18);
    border-radius: 4px;
  }

  /* ── PERSISTENT VIDEO BG (kept behind everything) ─────────────── */
  video.persistent-bg {
    position: fixed; top: 0; left: 0;
    width: 100vw; height: 100vh;
    object-fit: cover; z-index: -1;
    pointer-events: none;
    filter: contrast(1.05) saturate(0.9) brightness(0.85);
  }

  /* ── TYPOGRAPHY ───────────────────────────────────────────────── */
  h1 {
    font-size: 40px; font-weight: 600; letter-spacing: -0.022em;
    color: var(--ink); margin: 0 0 18px; line-height: 1.08;
  }
  h2 {
    font-size: 22px; font-weight: 500; letter-spacing: -0.008em;
    color: var(--ink-soft); margin: 0 0 16px; line-height: 1.3;
  }
  h3 {
    font-size: 18px; font-weight: 500; color: var(--ink);
    margin: 0 0 8px;
  }
  p, li { color: var(--ink-soft); margin: 6px 0; }
  strong { color: var(--ink); font-weight: 600; }
  em { color: var(--phosphor); font-style: normal; }
  a {
    color: var(--phosphor-cool);
    text-decoration: none;
    border-bottom: 1px dashed rgba(34, 211, 238, 0.4);
    transition: border-color 0.15s;
  }

  /* ── INLINE CODE ──────────────────────────────────────────────── */
  code {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.86em; font-weight: 500;
    background: rgba(245, 165, 36, 0.10);
    color: var(--phosphor);
    padding: 1px 7px;
    border-radius: 3px;
    border: 1px solid rgba(245, 165, 36, 0.22);
  }

  /* ── CODE BLOCKS — terminal artifact ──────────────────────────── */
  pre {
    background: rgba(0, 0, 0, 0.48);
    border: 1px solid var(--hairline-2);
    border-left: 2px solid var(--phosphor);
    border-radius: 6px;
    padding: 22px 24px 18px;
    font-size: 16px;
    line-height: 1.55;
    margin: 14px 0;
    box-shadow: inset 0 0 80px rgba(0,0,0,0.4), 0 4px 20px rgba(0,0,0,0.3);
    position: relative;
    font-feature-settings: 'liga', 'calt';
  }
  pre::before {
    content: '$_';
    position: absolute; top: 8px; right: 14px;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    color: var(--phosphor); opacity: 0.55; letter-spacing: 0.20em;
  }
  pre code {
    background: none; border: none; padding: 0;
    color: var(--phosphor-green);
    font-size: inherit;
  }

  /* ── TABLES — research data displays ──────────────────────────── */
  /* One table system used across the deck:
     - Mono-cap phosphor headers, hairline rows, no vertical lines
     - Top-aligned cells so multi-line values don't shift the label
     - Tabular nums for clean number columns
     - No hover, no striping — printed-paper feel */
  table {
    width: 100%;
    border-collapse: collapse;
    border-spacing: 0;
    font-size: 18px;
    font-variant-numeric: tabular-nums;
    margin: 14px 0;
    border-top: 1px solid var(--hairline-2);
  }
  th, td { border: 0; }
  th {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 11px;
    color: var(--phosphor);
    text-align: left;
    padding: 14px 16px 10px;
    border-bottom: 1px solid var(--hairline-2);
    background: transparent;
    vertical-align: bottom;
    white-space: nowrap;
  }
  td {
    padding: 11px 16px;
    color: var(--ink-soft);
    border-bottom: 1px solid var(--hairline);
    vertical-align: top;
    line-height: 1.5;
  }
  tr:last-child td { border-bottom: 1px solid var(--hairline-2); }
  /* Emphasis inside cells: use phosphor accent rather than going white,
     so tables stay in the same muted register as body copy. White was
     making tables read like a light-theme island against the dark deck. */
  td strong { color: var(--phosphor); font-weight: 600; }
  /* Chip-styled inline code inside table cells: lighter than body code
     so long URLs/paths don't dominate. */
  td code {
    background: rgba(245, 165, 36, 0.06);
    border-color: rgba(245, 165, 36, 0.18);
    font-size: 0.82em;
    padding: 1px 6px;
  }
  /* When a table is purely 2-column key-value (no headers in source),
     hide the empty thead row Marp emits from `| | |`. */
  table thead:has(th:empty:only-child) { display: none; }
  table thead tr:has(> th:empty + th:empty) { display: none; }

  /* ── BLOCKQUOTE — pull quote ──────────────────────────────────── */
  blockquote {
    border-left: 2px solid var(--phosphor-cool);
    background: rgba(34, 211, 238, 0.05);
    padding: 14px 22px;
    margin: 18px 0;
    color: var(--ink);
    font-style: normal;
    font-size: 0.96em;
    border-radius: 0 4px 4px 0;
  }
  blockquote p { color: var(--ink); margin: 0; }
  blockquote em { color: var(--phosphor-cool); font-style: italic; }
  blockquote strong { color: var(--ink); }

  /* ── TAG / CHIP ───────────────────────────────────────────────── */
  .tag {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    background: rgba(245, 165, 36, 0.08);
    color: var(--phosphor);
    border: 1px solid rgba(245, 165, 36, 0.30);
    border-radius: 3px;
    padding: 2px 9px;
    font-size: 11px; font-weight: 500;
    letter-spacing: 0.18em; text-transform: uppercase;
  }

  /* ── HEADER / FOOTER / PAGINATION CHIP ────────────────────────── */
  header, footer {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-mute);
    opacity: 0.65;
    padding: 18px 32px;
  }
  header::before {
    content: '◉ ';
    color: var(--phosphor);
    margin-right: 6px;
  }
  /* Marp pagination — reposition + restyle */
  section::after {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.20em !important;
    color: var(--ink-mute) !important;
    bottom: 22px !important;
    right: 32px !important;
    opacity: 0.7;
  }

  /* ── COVER (lead) ─────────────────────────────────────────────── */
  section.lead {
    text-align: left;
    justify-content: center;
    padding: 72px 96px;
    background-color: rgba(10, 12, 16, 0.42) !important;
  }
  section.lead h1 {
    font-size: 60px; font-weight: 700; letter-spacing: -0.032em;
    line-height: 1.02;
    background: linear-gradient(180deg, #ffffff 0%, var(--phosphor) 160%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
    max-width: 78%;
  }
  section.lead h3 {
    color: var(--ink-soft); font-weight: 400; font-size: 22px;
    letter-spacing: -0.005em; margin-top: 14px; max-width: 70%;
  }
  section.lead blockquote {
    margin-top: 28px;
    max-width: 75%;
  }
  section.lead header, section.lead footer { opacity: 0.4; }

  /* ── DIVIDER — full-bleed video moment ────────────────────────── */
  section.divider {
    background-color: var(--bg-panel-vbg) !important;
    text-align: left;
    justify-content: center;
    padding: 80px 96px;
  }
  section.divider h2 {
    color: var(--phosphor);
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px; letter-spacing: 0.32em;
    text-transform: uppercase;
    font-weight: 500;
    margin-bottom: 18px;
  }
  section.divider h2::before {
    content: '╱╱  ';
    color: var(--phosphor); opacity: 0.6;
  }
  section.divider h1 {
    font-size: 64px; font-weight: 600; letter-spacing: -0.030em;
    line-height: 1.0; max-width: 82%;
  }
  section.divider h3 {
    color: var(--ink-soft); font-weight: 400; font-size: 24px;
    margin-top: 22px; max-width: 70%;
    letter-spacing: -0.005em;
  }
  section.divider p {
    color: var(--ink-mute);
    font-family: 'JetBrains Mono', monospace; font-size: 13px;
    letter-spacing: 0.14em; margin-top: 22px;
    text-transform: uppercase;
  }

  /* ── VIDEO-BG modifier — even more transparent ────────────────── */
  section.video-bg {
    background-color: var(--bg-panel-vbg) !important;
  }

  /* ── TIGHT / TIGHTER — denser content ─────────────────────────── */
  section.tight  { font-size: 21px; padding: 48px 64px; }
  section.tight h1 { font-size: 32px; margin-bottom: 12px; }
  section.tight h2 { font-size: 18px; margin-bottom: 10px; }
  section.tight pre { font-size: 14px; line-height: 1.5; padding: 16px 18px; }
  section.tight table { font-size: 16px; }
  section.tight th { padding: 10px 12px 7px; }
  section.tight td { padding: 7px 12px; }
  section.tight blockquote { padding: 10px 18px; margin: 12px 0; font-size: 0.92em; }
  section.tight p, section.tight li { margin: 0.30em 0; }

  section.tighter { font-size: 19px; padding: 40px 56px; }
  section.tighter h1 { font-size: 28px; margin-bottom: 10px; }
  section.tighter h2 { font-size: 16px; margin-bottom: 8px; }
  section.tighter pre { font-size: 13px; line-height: 1.45; padding: 12px 16px; }
  section.tighter table { font-size: 15px; }
  section.tighter blockquote { padding: 8px 16px; margin: 8px 0; font-size: 0.9em; }
  section.tighter p, section.tighter li { margin: 0.20em 0; }

  /* ── PATTERN SLIDE — left rule + diagram-aware ────────────────── */
  section.pattern { font-size: 21px; padding: 48px 64px 56px; }
  section.pattern h1 {
    font-size: 30px; font-weight: 600;
    border-left: 2px solid var(--phosphor);
    padding-left: 18px;
    margin-bottom: 14px;
  }
  section.pattern blockquote {
    background: transparent;
    border-left: 2px solid var(--ink-mute);
    color: var(--ink-soft);
    font-size: 17px;
    padding: 4px 18px;
    margin: 4px 0 14px 0;
  }
  section.pattern blockquote em {
    color: var(--phosphor-cool);
    font-style: italic;
  }
  section.pattern img {
    display: block; margin: 10px auto 14px;
    max-height: 260px;
  }
  /* Re-theme line-art SVG diagrams to match palette */
  section.pattern img[src$=".svg"] {
    filter:
      invert(0.92)
      hue-rotate(180deg)
      saturate(0.55)
      brightness(1.05)
      drop-shadow(0 2px 8px rgba(245,165,36,0.10));
  }
  section.pattern .ref {
    color: var(--ink-mute);
    font-size: 12px;
    margin-top: 14px;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
    border-top: 1px solid var(--hairline);
    padding-top: 12px;
  }
  section.pattern .ref a {
    color: var(--ink-soft);
    border-bottom-color: rgba(177, 186, 196, 0.35);
  }
  section.pattern .ref strong {
    color: var(--phosphor);
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-size: 0.9em;
    margin-right: 6px;
  }

  /* ── LOOP DIAGRAM SLIDE — bigger, also re-themed ──────────────── */
  section img[src$="loop.svg"] {
    filter:
      invert(0.92)
      hue-rotate(180deg)
      saturate(0.55)
      brightness(1.05)
      drop-shadow(0 4px 18px rgba(34,211,238,0.10));
    margin: 8px auto 14px;
  }

  /* ── SCREENSHOT IMAGES (output styles) ────────────────────────── */
  section img[src*="images/"] {
    box-shadow:
      0 16px 60px rgba(0,0,0,0.6),
      0 0 0 1px var(--hairline-2);
    border-radius: 4px;
  }

  /* ── SPEC CARD — closer ───────────────────────────────────────── */
  /* Treats the 2-column key-value table as a spec sheet:
     left column becomes a fixed-width mono-caps label rail,
     right column carries the value at body-text size. */
  section.spec {
    background-color: var(--bg-panel-vbg) !important;
  }
  section.spec h1 {
    font-size: 30px;
    font-family: 'Geist', sans-serif;
    border-bottom: 1px solid var(--hairline-2);
    padding-bottom: 12px;
    margin-bottom: 16px;
  }
  section.spec h3 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--phosphor);
    margin-top: 18px;
    margin-bottom: 8px;
  }
  section.spec table {
    border-top: 1px solid var(--hairline-2);
    margin: 6px 0 14px;
  }
  section.spec table thead { display: none; }
  section.spec table td {
    padding: 9px 14px;
  }
  section.spec table td:first-child {
    width: 130px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--phosphor);
    padding-top: 12px;
    white-space: nowrap;
  }
  section.spec table td:first-child strong {
    color: inherit;
    font-weight: 500;
  }
  section.spec table td:nth-child(2) {
    color: var(--ink-soft);
    font-size: 16px;
  }
  section.spec pre {
    border-left-color: var(--phosphor-cool);
    font-size: 13px;
  }
  section.spec pre::before { content: 'BIBTEX'; }

  /* ── HIDE pagination on lead ──────────────────────────────────── */
  section.lead::after { display: none; }
---

<!--
RUNBOOK DEL DEMO — LEER ANTES DE PRESENTAR
==========================================
Versión "_es": el contenido visible está en inglés (alineado con el código
y los identificadores del repo); las notas del orador están en español
rioplatense para el presentador hispanohablante.

Esta versión es una variante de demo_merged.md donde las EXPLICACIONES
LARGAS (los párrafos "El patrón —") fueron movidas desde el cuerpo visible
hacia notas del orador. Resultado: slides más limpios visualmente, y todo
el peso narrativo lo cargás vos al hablar — apoyado por estas notas.

Pre-trabajo en la terminal:
  1. cd multillm-adversarial-convergence
  2. Abrir: configs/research/localstack_alternatives_copilot_codex.yaml
  3. Tener en pestañas del browser:
       docs/showcase/localstack-alternatives/raw/report.html
       docs/showcase/localstack-alternatives/paper/report.html
       docs/showcase/localstack-alternatives/technical/report.html
  4. Listo a mano: cat docs/showcase/localstack-alternatives/technical/audit_trail.jsonl | python3 -m json.tool | head -60
  5. Pre-render de diagramas: ./build.sh  (genera patterns/*.svg + loop.svg)

TIMING DE SLIDES (~45-50 min full)
  Slides 1–4    (intro + origen + loop)            ~5 min
  Slide  5      (divisor — patrones)                ~10 seg
  Slide  6      (por qué importan los patrones)    ~2 min
  Slides 7–17   (los 11 patrones, ~1 min cada uno) ~12 min
  Slide  18     (lattice de estrategias)            ~3 min
  Slide  19     (divisor — demo)                    ~10 seg
  Slides 20–21  (config + dry-run)                  ~3 min
  Slide  22     (divisor — adversarial)             ~10 seg
  Slides 23–24  (crítico + curva de score)          ~5 min
  Slides 25–28  (artefactos + 3 estilos de output)  ~5 min
  Slides 29–31  (replay + trust + costo)            ~3 min
  Slides 32–33  (takeaways + cómo probarlo)         ~2 min

NOTA DE STAGING: avisale al público en el slide 1. Nunca escondas que es
una corrida grabada que se reproduce a velocidad — la honestidad es parte
del mensaje.
-->

<!-- _class: lead video-bg -->
<!-- _paginate: false -->

<script>
// Inject a single <video> at body level so it persists across slide nav
// and never restarts. Sections with class `video-bg` are transparent and
// reveal it; other sections cover it with their opaque background.
(function () {
  if (document.querySelector('video.persistent-bg')) return;
  var v = document.createElement('video');
  v.className = 'persistent-bg';
  v.src = 'animation-veryslow.mp4';
  v.autoplay = true;
  v.muted = true;
  v.loop = true;
  v.setAttribute('playsinline', '');
  v.setAttribute('muted', '');
  document.body.appendChild(v);
})();
</script>

# Multi-LLM Adversarial Convergence Framework

### Make competing LLMs argue until they converge on the best answer

<br>

> **Staged demo** — this is a real run played back at speed.
> All artifacts shown are live outputs from the actual execution.

<!--
NOTAS DEL ORADOR (slide 1 — cover):

Antes de arrancar: dejá claro que esto es un demo grabado que se reproduce a
velocidad. No estamos esperando que un modelo piense en vivo — eso sería
imposible de presentar bien en 30 minutos. Pero todos los artefactos que vas
a ver salieron de una corrida real: mismo config, mismos backends, mismo
audit trail. Nada está mockeado. Nada está editado a mano para que quede
lindo.

La idea central — "que los LLMs discutan hasta converger" — la van a ver
materializada en cada slide. No es una metáfora; es literalmente lo que
hace el sistema: un backend propone, otro distinto critica, un tercero
arbitra, y el ciclo se repite hasta que el score deja de mejorar.

Si la audiencia es técnica, hacé énfasis en el "different model families".
Si es producto/management, hacé énfasis en el "audit every claim".
-->

---
<!-- TIMING: 1 min — el problema en una sola oración antes de cualquier historia de origen -->

## The problem

Single-model research is **non-deterministic and unverifiable**.
One LLM, one pass, one perspective.

> You can't know what it missed, what it fabricated with confidence, or whether a different model would have reached the same conclusion.

**This framework's answer:**

- Run multiple backends on the same topic
- Make them **score, critique, and argue with each other**
- Keep only what survives adversarial review
- Emit a full evidence trail so you can audit every claim

<!--
NOTAS DEL ORADOR (slide 2 — el problema):

Acá tenés que plantar bandera: el problema NO es "los LLMs alucinan a veces".
El problema es estructural — un solo modelo no te da forma de saber qué le
faltó ver, qué inventó con confianza, ni si otro modelo distinto habría
llegado a la misma conclusión. Es un punto ciego de epistemología, no de
prompt engineering.

La frase clave para repetir: "non-deterministic and unverifiable". Esas son
dos palabras distintas — no determinístico (la salida varía entre corridas)
y no verificable (no podés auditar el razonamiento). Las dos son problemas
separados y este framework ataca a las dos.

Cuando llegues a "make them score, critique, and argue with each other",
hacé una pausa. Es la idea central de todo el sistema. Lo que sigue son
detalles de implementación.
-->

---
<!-- TIMING: 2 min — historia de origen, ahora que ya saben qué están viendo -->

## Origin: Karpathy's `autoresearch`

The loop isn't original. [Andrej Karpathy's `autoresearch`](https://github.com/karpathy/autoresearch) runs:

> *modify code → train 5 min on GPU → measure loss → keep or revert*

The insight: **this shape applies to anything you can score**.

| Karpathy's `autoresearch` | This framework |
|---|---|
| GPU training run | LLM backend call |
| Loss function | Heuristic 40% + LLM judge 60% |
| Neural network weights | Knowledge corpus |
| ~5 min per iteration | One backend call per iteration |
| Stops when loss plateaus | Stops on `max_iterations` or `target_dimensions_total` |

Same loop. Different substrate: **knowledge instead of weights**.

<!--
NOTAS DEL ORADOR (slide 3 — origen Karpathy):

Importante reconocer que el loop no lo inventamos nosotros. Karpathy lo
publicó como `autoresearch` para entrenamiento de redes neuronales. La
mecánica es simple: modificás código, entrenás 5 minutos en GPU, medís
la loss, y decidís keep-or-revert. Si mejoró, lo guardás; si no, lo
descartás. Iterás.

El insight transferible — y este es el punto que tenés que machacar — es
que esta forma del loop no es exclusiva del entrenamiento. Aplica a CUALQUIER
cosa que puedas puntuar. Investigación con LLMs es una de esas cosas.

Cuando recorras la tabla, andá despacio. Cada fila es una analogía 1-a-1.
GPU run → llamada a backend. Loss → score híbrido (heurística + judge).
Pesos de la red → corpus de conocimiento. Es la misma máquina con otro
sustrato: el sustrato son weights en Karpathy, knowledge acá.

Si te preguntan "¿por qué heurística 40 / judge 60?" — respondé: el judge
solo puede ser gameado (un modelo aprende a escribir para el judge). La
heurística es determinística y model-agnostic. Combinadas, son más difíciles
de explotar. Vamos a profundizar en LLM-as-Judge en el slide 8.
-->

---
<!-- TIMING: 2 min — diagrama del loop. Bajá la velocidad acá. Es el modelo mental para todo lo que sigue. -->

## The loop

![w:1150](loop.svg)

<br>

| | |
|---|---|
| **Critique** (purple) | A *different* backend — different priors, different blind spots |
| **Decide** (amber) | KEEP grows the corpus · DISCARD retries the same dimension |
| **Compress** (teal) | Every N iterations: distill, drop noise, bound context cost |

Stops on `Ctrl+C`, `max_iterations`, or `target_dimensions_total`.

<!--
NOTAS DEL ORADOR (slide 4 — el loop):

Este es EL slide más importante de toda la primera parte. Es el modelo
mental que vas a referenciar implícitamente en cada explicación que sigue.
No tengas apuro acá. Mostrá el diagrama, dejá que lo lean, y después
recorré los tres elementos coloreados.

Critique (violeta): el crítico SIEMPRE es un backend distinto al que
produjo. No es self-evaluation. Diferentes priors → diferentes blind spots.
Si Claude tiene un sesgo, GPT no lo comparte (y al revés). Esa diferencia
es exactamente lo que querés capturar.

Decide (ámbar): KEEP hace crecer el corpus, DISCARD hace que el sistema
reintente la misma dimensión con una hipótesis distinta. No es "fallaste,
seguís" — es "no convergió, probá otro ángulo".

Compress (turquesa): cada N iteraciones (default: 4) el agente reescribe
su propio corpus, podando lo que ya no aporta. Sin esto, los runs explotan
en costo de tokens y el modelo pierde foco. Es rank-and-prune forzado.

Stopping criteria: tres opciones. Ctrl+C (intervención manual), max
iterations (presupuesto), o target dimensions cubiertas (objetivo). Lo que
ocurra primero.
-->

---
<!-- _class: divider video-bg -->
<!-- TIMING: transición, 10 seg -->

## I · PATTERNS

# Agentic Design Patterns

### Engine · Topology · Guardrails

*11 named patterns from the research literature — each cited, each replaceable.*

<!--
NOTAS DEL ORADOR (slide 5 — divisor patrones):

Transición rápida. Acá empieza la parte densa: los 11 patrones. Avisá que
se van a mostrar uno por slide, agrupados en tres capas (Engine, Topology,
Guardrails). Cada uno tiene una cita canónica.

Si la audiencia es senior técnica, decí: "vamos a ver una taxonomía
ejecutable, no una lista de buzzwords".
Si es mixta, decí: "cada cosa que parece un truco tiene un nombre y un
paper detrás".
-->

---
<!-- _class: tight -->
<!-- TIMING: 2 min — preámbulo antes del desfile de patrones. ¿Por qué nombrarlos? -->

## Why these patterns matter

This codebase is **not a collection of hacks**.

1. **Replaceability** — when a pattern is named, swapping the implementation is mechanical
2. **Defensibility** — code review can ask *"is this Evaluator-Optimizer or Reflection?"* instead of *"is this fine?"*
3. **Onboarding** — new contributors recognise shapes; they don't have to reverse-engineer intent

> 11 patterns: **engine** (3) + **topology** (5) + **guardrails** (3).

<!--
NOTAS DEL ORADOR (slide 6 — por qué importan los patrones):

El framing acá es importante. La razón por la que cada componente del
sistema mapea a un patrón con nombre y referencia bibliográfica NO es por
academicismo — es por tres beneficios concretos en la operación del código.

Replaceability — cuando algo tiene nombre, intercambiarlo es mecánico. Si
mañana querés cambiar el judge de codex-cli a gemini-api, no rediseñás
nada: cambiás el binding del role en el config. El patrón "Multi-Agent
Role Topology" te da exactamente esa indirección.

Defensibility — en code review, en vez de discutir "¿esto está bien?"
discutís "¿esto es Evaluator-Optimizer o es Reflection?". Conversación más
corta, más precisa, menos sujeta a opinión personal.

Onboarding — alguien que llega nuevo al repo reconoce las formas. No tiene
que ingeniería-inversa cada decisión. Si vio Evaluator-Optimizer en otro
proyecto, lo reconoce acá y arranca productivo más rápido.

Los 11 patrones no son toda la teoría agéntica que existe — son el
subconjunto que ESTE framework efectivamente compone. Engine son los 3
que hacen que una iteración tenga sentido. Topology son los 5 que dicen
cómo se conectan los backends. Guardrails son los 3 que evitan que el
sistema haga lo que no debería.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 1: el outer loop -->

## 1 · Evaluator-Optimizer

> *The outer loop. Propose, score, keep or discard, repeat.*

![w:880](patterns/01-evaluator-optimizer.svg)

**In this codebase**
- `src/research_loop.py` — owns the iteration cycle
- `src/scorer.py` — composite score (heuristic 40% + judge 60%); see `IterationScore`
- `KEEP` vs `DISCARD` decision recorded per iteration in `audit_trail.jsonl`

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

<!--
NOTAS DEL ORADOR (slide 7 — Pattern 1: Evaluator-Optimizer):

EL PATRÓN — Es el outer loop más simple que existe en sistemas agénticos.
Un generador produce candidatos. Un evaluador los puntúa contra un
objetivo. El sistema se queda con los que tienen score alto y descarta
(o reescribe) los demás. El loop corre hasta que el score se aplana o
hasta que se agota un presupuesto (iteraciones, tiempo, costo).

La pieza que muchos pasan por alto: el evaluador y el generador NO tienen
que ser el mismo modelo. De hecho, idealmente NO lo son — pero ese tema
lo desarrollamos en el patrón siguiente (LLM-as-Judge).

En este repo: research_loop.py es el dueño del ciclo. scorer.py implementa
el score híbrido (40% heurística determinística + 60% judge LLM, valores
configurables). Cada decisión KEEP o DISCARD queda registrada en
audit_trail.jsonl como evento estructurado — eso te permite reconstruir
exactamente qué decidió el sistema y por qué.

Referencia canónica: el paper de Anthropic "Building Effective Agents".
Es la base teórica más citada para este patrón.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Patrón 2: el corazón del modelo de confianza. Demorá un beat en independencia. -->

## 2 · LLM-as-Judge

> *A different model scores the candidate. No self-grading.*

![w:920](patterns/02-llm-as-judge.svg)

**In this codebase**
- `src/scorer.py` — `judge_response()` calls a non-producer backend
- Hybrid: 40% deterministic heuristic + 60% LLM judge (configurable via `scoring.weights`)
- Multi-judge mode: `evaluation.judges = [...]` enables consensus + disagreement detection (`detect_judge_disagreement()`)

<span class="ref">**Reference:** [agentic-design.ai — LLM-as-Judge](https://agentic-design.ai/patterns/reflection/llm-as-judge) · [arXiv 2410.10934](https://arxiv.org/abs/2410.10934)</span>

<!--
NOTAS DEL ORADOR (slide 8 — Pattern 2: LLM-as-Judge):

EL PATRÓN — Acá hay un principio que parece obvio pero que se viola
constantemente: el modelo que PRODUCE una salida no puede puntuarla bien.
Self-evaluation tiene sesgo conocido hacia la verbosidad y la confianza.
El modelo se cree sus propias respuestas.

La solución: un modelo separado, idealmente de otra familia, evalúa la
salida contra un rubric. Su score es UNA de las entradas a la decisión
keep/discard — no es la única, hay también una heurística determinística.

Por qué híbrido (40 heurística / 60 judge): un judge LLM puro se puede
gamear. Si el productor aprende a "escribir para el judge", el sistema
colapsa. La heurística es determinística (chequea cobertura, densidad de
citas, completitud por dimensión) — no se gamea. Las dos juntas son más
duras de explotar que cualquiera por separado.

Modo multi-judge: si configurás varios judges, el sistema detecta
desacuerdo entre ellos. Eso es señal de que la dimensión es ambigua o
que un judge tiene sesgo — útil para flagging temprano.

Referencias: agentic-design.ai tiene la mejor explicación práctica;
arXiv 2410.10934 es el paper de fondo sobre judge bias.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 3: por qué importa acotar el contexto. Rank-and-prune forzado. -->

## 3 · Reflection / Self-Compression

> *Every N iterations: distill the corpus, drop noise.*

![w:1080](patterns/03-reflection-compression.svg)

**In this codebase**
- `compression_interval` config flag (default: every 4 iterations)
- The agent re-reads its own corpus and emits a distilled version
- Audit event: `corpus_compressed` with before/after token counts

<span class="ref">**Reference:** [Andrew Ng — Agentic Patterns](https://www.deeplearning.ai/the-batch/how-agents-can-improve-llm-performance/)</span>

<!--
NOTAS DEL ORADOR (slide 9 — Pattern 3: Reflection / Self-Compression):

EL PATRÓN — La iteración naive crece el contexto monotónicamente. Cada
claim que sobrevive el KEEP se agrega a la memoria de trabajo. Sin
compresión, los runs explotan: el costo de tokens se va al carajo, el
modelo pierde foco, y la relación señal/ruido cae.

La compresión es un paso forzado de "rank-and-prune": el agente vuelve a
leer su propio corpus y lo reescribe, quedándose solo con lo que él
juzga load-bearing. No es resumir — es priorizar. Lo que se cae, se cae
con registro de auditoría.

Esto NO es opcional para runs largos. Sin compression_interval, una
investigación de 20 iteraciones puede llegar a usar 10x los tokens que
una bien comprimida, y la calidad del último claim se degrada porque el
modelo está sumergido en ruido.

En este repo: el flag es compression_interval (default 4). El audit
event corpus_compressed registra los token counts antes y después,
así podés ver cuánto se podó.

Referencia: el batch de Andrew Ng sobre agentic patterns. La sección
de Reflection es la canonical.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 4: quién es dueño del lifecycle. Workers que no llaman workers. -->

## 4 · Orchestrator / Subagents

> *One owner of lifecycle. Many narrow-contract workers.*

![w:780](patterns/04-orchestrator-subagents.svg)

**In this codebase**
- `src/orchestrator.py` — the only owner of phase transitions, convergence checks, compression triggers
- `src/backends/` — adapters with a single contract: `run(prompt) → response`
- Backends never call each other; they only return to the orchestrator

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

<!--
NOTAS DEL ORADOR (slide 10 — Pattern 4: Orchestrator / Subagents):

EL PATRÓN — Centralizá el control flow en un solo componente. Los backends
son trabajadores con contrato angosto: reciben una tarea, devuelven un
resultado, y NO tienen awareness del lifecycle más amplio. No saben en
qué iteración están, no saben qué backend corre antes o después, no
saben si esto va a un judge.

Esa restricción los hace reemplazables, testeables, y sobre todo evita
que el estado cross-cutting se filtre dentro de los adaptadores de
transporte. Si copilot-cli cambia su API mañana, lo único que tocás es
el adapter — la lógica del loop no se entera.

Regla dura: los backends NUNCA se llaman entre sí. Solo retornan al
orchestrator. Si necesitás encadenar dos backends, eso es lógica del
orchestrator, no del backend.

orchestrator.py es el ÚNICO dueño de las transiciones de fase, los
chequeos de convergencia, y los triggers de compresión. Si ves
control flow en otra parte, es un bug arquitectural.

Referencia: Anthropic "Building Effective Agents" tiene la formulación
canónica de orchestrator-workers.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 5: roles vs modelos. La superficie de swap. -->

## 5 · Multi-Agent Role Topology

> *Configure roles, not models. Swap backends without changing logic.*

![w:900](patterns/05-role-topology.svg)

**In this codebase**
- `configs/research/<topic>.yaml` — `execution.backends` map roles to backend IDs
- `src/config.py` — `BackendsConfig` schema; validates role completeness
- Role names appear in audit events: `role=judge backend=codex-cli`

<span class="ref">**Reference:** [arXiv 2405.10467 — Multi-Agent Role Topology](https://arxiv.org/abs/2405.10467)</span>

<!--
NOTAS DEL ORADOR (slide 11 — Pattern 5: Multi-Agent Role Topology):

EL PATRÓN — Los nombres `primary`, `judge`, `utility`, `research[]` son
abstracciones que el código razona. Cada uno se bindea a un backend
concreto en config time. El mismo código del orchestrator funciona si
hoy `judge` es codex-cli y mañana es gemini-api. Esa indirección ES la
superficie de swap.

Sin este patrón, cambiar el judge significa modificar el código del
orchestrator. Con este patrón, es cambiar una línea de YAML. La diferencia
es enorme cuando estás iterando experimentalmente con qué modelo es mejor
en qué rol.

Detalle de implementación: BackendsConfig valida que TODOS los roles
necesarios estén bindeados antes de arrancar. Si te falta el role `judge`
y la estrategia lo necesita, fallás temprano con error claro — no en
medio del run cuando ya gastaste tokens.

Los nombres de role aparecen en cada evento de audit. role=judge
backend=codex-cli — eso te permite filtrar logs por rol semántico, no
solo por backend técnico. Útil cuando querés ver "todo lo que hizo el
critic" sin importar qué modelo lo cumplió en esta corrida.

Referencia: arXiv 2405.10467 es la formalización académica del patrón.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 6: dispatch por persona. -->

## 6 · Routing / Specialist Dispatch

> *Each dimension goes to the backend best suited for it.*

![w:920](patterns/06-routing-specialist.svg)

**In this codebase**
- `src/strategy.py` — `specialist` strategy
- Each dimension declares a persona in config; persona → backend lookup at dispatch time
- Falls back to `primary` if no specialist matches

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

<!--
NOTAS DEL ORADOR (slide 12 — Pattern 6: Routing / Specialist Dispatch):

EL PATRÓN — Trabajo distinto necesita priors distintos. Una pregunta de
breadth ("¿cuáles son las alternativas a X?") se beneficia de un modelo
con recall amplio. Una pregunta de precisión-crítica ("¿esta cita
realmente sostiene este claim?") se beneficia de un modelo entrenado
adversarial.

El router mira la persona declarada por la dimensión y dispatcha al
backend correspondiente. Si una dimensión no tiene specialist matchable,
cae al primary — fail-safe en vez de fail-stop.

Caso de uso típico: en una investigación de 8 dimensiones, podés tener
2 que pidan "broad-recall", 4 que pidan "precision-analyst", y 2 que
pidan "code-reviewer". Cada una se asigna al backend que la maneje
mejor. No estás obligado a usar un solo modelo para todo.

Cuándo NO usar specialist: cuando la audiencia te pidió una sola
"voz" coherente en el output final. En ese caso, mejor ensemble o serial
con un único primary.

Referencia: Anthropic "Building Effective Agents" — sección sobre
routing, que es el patrón general del cual specialist dispatch es una
especialización.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 7: reducción de varianza vía redundancia. -->

## 7 · Parallelization (Ensemble)

> *Fan out to all backends in parallel. Merge via judge.*

![w:880](patterns/07-parallel-ensemble.svg)

**In this codebase**
- `src/strategy.py` — `ensemble` and `parallel` strategies
- `concurrent.futures.ThreadPoolExecutor` — bounded parallelism
- Judge selects best response or synthesises an ensemble answer

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

<!--
NOTAS DEL ORADOR (slide 13 — Pattern 7: Parallelization / Ensemble):

EL PATRÓN — Reducción de varianza por redundancia. Corrés la MISMA tarea
en N backends simultáneamente. Las respuestas van a divergir en formas
interesantes — y esa divergencia ES la información que querés.

Después un judge elige la más fuerte, o un paso de vote/merge las combina.
Cuál estrategia depende de la tarea: para investigación abierta, merge
suele ganar (combinás coverage). Para preguntas con respuesta única,
vote/judge suele ganar (filtrás errores).

Cuándo conviene ensemble: cuando el costo de una respuesta equivocada es
alto Y el presupuesto te permite la redundancia. Si estás escribiendo un
ADR que va a guiar 6 meses de trabajo, gastar 3x los tokens para tener
varianza más baja es una compra fácil. Si estás explorando una idea
casual, no.

Detalle de impl: usamos ThreadPoolExecutor con paralelismo acotado.
No queremos que un ensemble de 4 backends mate al rate limit de uno y
falle todo el run.

Referencia: Anthropic — sección de parallelization patterns.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 8: especialización por etapa. -->

## 8 · Prompt Chaining (Serial)

> *Backends take turns. Each stage receives the previous stage's output.*

![w:960](patterns/08-prompt-chaining-serial.svg)

**In this codebase**
- `src/strategy.py` — `serial` strategy
- Stage N+1's prompt includes stage N's full output as context
- Used when stages have asymmetric specialisations (research → critique → synthesis)

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

<!--
NOTAS DEL ORADOR (slide 14 — Pattern 8: Prompt Chaining / Serial):

EL PATRÓN — Especialización por ETAPA, no por tarea. Un backend investiga,
el próximo critica, el próximo refina. Cada etapa opera sobre el output
de la anterior, así que la cadena acumula contexto. Más barato que
ensemble (no son llamadas paralelas, no hay redundancia) pero más lento
end-to-end (las etapas son secuenciales, no se solapan).

Cuándo usar serial sobre ensemble: cuando las etapas tienen
especializaciones asimétricas. Investigar y criticar son habilidades
distintas — querés que el research-stage NO esté pensando en críticas, y
el critique-stage NO esté pensando en producir contenido nuevo. La
separación de responsabilidades es la ventaja.

Cuándo NO usar serial: cuando la audiencia espera una respuesta rápida.
Cada etapa adiciona latencia, y un chain de 4 etapas con 30 segundos
cada una son 2 minutos largos.

En el repo, la etapa N+1 recibe el output COMPLETO de la N como contexto
en el prompt. Eso hace que la cadena sea coherente, pero también hace
que el costo crezca con cada etapa. Por eso el patrón de Reflection /
Compression aplica con fuerza acá si la cadena es larga.

Referencia: Anthropic — el patrón de chaining es uno de los más antiguos
y mejor documentados.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Patrón 9: la estrategia del demo. Distinto RLHF = distintos blind spots. -->

## 9 · Adversarial Critique

> *Researcher · Critic · Arbitrator — across different model families.*

![w:880](patterns/09-adversarial-critique.svg)

**In this codebase**
- `src/strategy.py` — `adversarial` strategy (used in the demo run)
- Three roles: `researcher`, `critic`, `arbitrator` — each a different backend family
- Audit log records every critique flag and arbitrator decision

<span class="ref">**Reference:** [arXiv 2305.19118 — Multi-Agent Debate](https://arxiv.org/abs/2305.19118)</span>

<!--
NOTAS DEL ORADOR (slide 15 — Pattern 9: Adversarial Critique):

EL PATRÓN — Variante en forma de debate del serial chaining. El researcher
propone claims; el critic — DELIBERADAMENTE de otra familia de modelos —
busca errores, citas débiles, gaps lógicos; el arbitrator (otra familia
distinta de nuevo) emite un veredicto.

La pieza clave: "different RLHF training produces different blind spots".
Cada modelo fue entrenado por humanos distintos con feedback distinto, así
que internalizó sesgos distintos. Las debilidades de Claude son visibles
para GPT, y al revés. Si los tres backends fueran del mismo proveedor,
este patrón sería inútil — estarías triangulando con tres versiones del
mismo blind spot.

Esta es LA estrategia que usa el demo run que vamos a ver. Tres roles,
tres familias: claude-cli investiga, codex-cli critica, codex-cli
arbitra. Y vas a ver concretamente qué encontró el critic — errores
factuales reales, no comentarios de estilo.

El audit log registra cada flag del critic y cada decisión del
arbitrator. Esa traza es lo que te permite reconstruir POR QUÉ una
hipótesis sobrevivió o fue descartada.

Referencia: arXiv 2305.19118 — el paper de Multi-Agent Debate. Es la
formalización académica del approach.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Patrón 10: sandbox como IAM. Anclá a preocupaciones empresariales. -->

## 10 · Tool Use + Sandboxed Execution

> *The capability registry is the agentic equivalent of an IAM policy.*

![w:920](patterns/10-tool-use-sandbox.svg)

**In this codebase**
- `src/policy/` — capability registry, sandbox executor, audit hooks
- Write boundary: `output/<run>/.workspace/` — outside is read-only
- Network policy: `web_only` (allowlisted endpoints) or `none`
- Audit events: `tool_denied`, `write_intent`, `network_intent`

<span class="ref">**Reference:** [Anthropic — Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)</span>

<!--
NOTAS DEL ORADOR (slide 16 — Pattern 10: Tool Use + Sandboxed Execution):

EL PATRÓN — Los agentes necesitan tools (web fetch, code execution,
file write) pero cada tool ensancha la superficie de ataque. El approach
de capability registry: cada tool se declara con sus capacidades; las
llamadas no clasificadas son denegadas por default.

Los writes a filesystem se scopean a un directorio sandbox. El acceso
de red se gating a `web_only` (endpoints en allowlist) o `none` (no hay
red en absoluto). Cada denial es auditable.

El framing que mejor le pega a audiencias enterprise: "el capability
registry es el equivalente agéntico de una IAM policy". Mismo principio
de least privilege, pero a nivel de tool en vez de a nivel de proceso.
Si tu audiencia maneja AWS o cualquier nube, ese paralelismo aterriza
inmediato.

Detalles concretos: el write boundary es output/<run>/.workspace/ — todo
lo que esté afuera es read-only para el agente. Network policy tiene dos
estados productivos: web_only con allowlist explícita, o none. Los audit
events tool_denied / write_intent / network_intent te dan trazabilidad
completa de TODO lo que el agente intentó hacer y qué se le negó.

Si te preguntan "¿se puede saltear?": no fácil. El sandbox executor
intercepta a nivel de syscall lo que puede; lo que no puede se intercepta
en el tool wrapper. Si un agente quiere escribir afuera del workspace,
el intento queda en el audit trail antes de ser rechazado.

Referencia: Anthropic "Writing Tools for Agents" tiene la guía
canónica de cómo declarar tools de forma segura.
-->

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Patrón 11: gates de fase. Las dos decisiones quedan registradas. -->

## 11 · Human-in-the-Loop (HITL)

> *Phase-transition gates. Operator approves before irreversible actions.*

![w:920](patterns/11-human-in-the-loop.svg)

**In this codebase**
- `src/policy/hitl.py` — phase-transition gate
- Configurable per-phase: `hitl.gates = [research_to_synthesis, plan_approve, ...]`
- Audit events: `hitl_approved`, `hitl_aborted` — both with operator identity

<span class="ref">**Reference:** [LangGraph — Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)</span>

<!--
NOTAS DEL ORADOR (slide 17 — Pattern 11: Human-in-the-Loop):

EL PATRÓN — Algunas acciones son demasiado consecuentes para confiárselas
a un agente plenamente autónomo: deploys, escrituras irreversibles,
gastos grandes. HITL inserta una pausa explícita en los bordes de fase;
el operador revisa los artefactos, los plan diffs, las estimaciones de
costo, y aprueba o aborta.

Punto clave: las DOS decisiones (approve y abort) se registran. No es solo
"tuvo permiso para seguir" — es "Juan aprobó esto a las 14:32 con esta
plan diff visible". Eso le da auditoría completa.

Caso de uso típico: en una investigación que termina escribiendo un ADR,
querés HITL en el borde research → synthesis. El operador chequea que
las dimensiones cubiertas tienen sentido, que el corpus se ve sano, y
recién ahí autoriza la generación del documento final.

NO es un patrón para producción autónoma 24/7 — es para flows donde
querés delegate-but-verify. Tiene latencia humana (puede pasar una hora
desde que el agente termina la fase research hasta que el operador
aprueba), así que diseñar el flow para que la pausa esté OK es parte del
costo.

Referencia: LangGraph tiene la documentación más práctica sobre HITL.
-->

---
<!-- _class: tight -->
<!-- TIMING: 3 min — composición. El demo run es una tupla sobre las capas. -->

## How they compose — the strategy lattice

| Layer | Patterns | Concern |
|---|---|---|
| **Engine** | Evaluator-Optimizer · LLM-as-Judge · Reflection | What makes a single iteration meaningful |
| **Topology** | Orchestrator · Role Topology · Routing · Parallel · Serial | How backends are wired and dispatched |
| **Guardrails** | Adversarial Critique · Sandbox · HITL | What prevents the agent from doing the wrong thing |

> **A configured strategy is a tuple over the layers.** Demo run = `Adversarial Critique` (guardrail) over `Serial Chaining` (topology) using `Evaluator-Optimizer + LLM-as-Judge` (engine), with `Sandbox` always on.

<!--
NOTAS DEL ORADOR (slide 18 — strategy lattice):

Acá unificás las 11 cajitas anteriores en una vista de capas. Los patrones
no son ortogonales — se layerean. Engine es lo que hace que una iteración
tenga sentido. Topology es cómo se conectan los backends. Guardrails es
qué evita que el sistema haga macanas.

La frase clave: "a configured strategy is a tuple over the layers". Cada
configuración real del sistema es UNA elección por capa. No hay "modo
adversarial" como botón único — adversarial es una elección de guardrail
que se compone con elecciones de topology y engine.

El demo que vamos a ver es: Adversarial Critique (guardrail) sobre Serial
Chaining (topology) usando Evaluator-Optimizer + LLM-as-Judge (engine),
con Sandbox siempre prendido. Esa tupla específica.

Si te preguntan "¿puedo combinar X con Y?" — generalmente sí. Las capas
son mix-and-match. Las únicas combinaciones imposibles son las que el
schema de config las rechaza explícitamente (por ejemplo, no tiene sentido
ensemble + serial al mismo tiempo).

El insight pedagógico: cuando alguien venga con un caso nuevo, el
ejercicio NO es "¿qué framework de AI uso?" — es "¿qué tupla de capas
compongo?". Eso es un cambio de framing importante.
-->

---
<!-- _class: divider video-bg -->
<!-- TIMING: transición, 10 seg -->

## II · DEMO

# Demo

### LocalStack alternatives — a real research question

*"LocalStack went fully paid. Should our team pay Pro or migrate to an open-source alternative?"*

<!--
NOTAS DEL ORADOR (slide 19 — divisor demo):

Transición. Se acaba la parte teórica, arranca el demo. Avisá que vamos a
ver una pregunta concreta — la migración de LocalStack — corrida con los
patrones que acabamos de explicar.

Si la audiencia tiene gente que conoce LocalStack, hacé énfasis en la
parte de "moving to a fully paid model" — la decisión es real, no
inventada para el demo. Si no conocen, contextualizá: LocalStack emula
servicios de AWS localmente, hace falta para CI/CD, y acaba de pasar
a modelo pago.
-->

---
<!-- TIMING: 2 min — mostrá el config en la terminal. Cosas que tenés que señalar:
  - strategy: adversarial
  - tres backends: claude-cli (primary), copilot-cli (researcher), codex-cli (adversary+judge)
  - 8 dimensiones, max 10 iteraciones
  - allowed_tools: tools web reales, no mockeados
-->

<!-- _class: tighter -->

## The config — three backends, adversarial strategy

```yaml
# configs/research/localstack_alternatives_copilot_codex.yaml
research:
  topic: >
    Compare alternatives to LocalStack for local AWS service emulation.
    LocalStack is moving to a fully paid model. Evaluate MiniStack, Floci,
    and other viable open-source alternatives.
  goal: >
    A decision-ready comparison for a team evaluating LocalStack Pro vs
    open-source migration. Include migration effort, service coverage gaps,
    and a clear recommendation.
  execution:
    strategy: adversarial
    backends:
      primary:   primary_reasoner    # claude-cli (Claude Code)
      research:  [research_coder]    # copilot-cli (GitHub Copilot)
      judge:     adversary_reasoner  # codex-cli   (GPT-5.4) ← critic + judge
      utility:   adversary_reasoner
    max_iterations: 10
    allowed_tools: "WebSearch,WebFetch,Read,Bash,Glob,Grep"
```

Three different model families. Critic and judge are **deliberately different** from the researcher.

<!--
NOTAS DEL ORADOR (slide 20 — config YAML):

Mostrá esto en la terminal real (con bat o tu editor) además del slide
si tenés tiempo. Las piezas a remarcar:

1. strategy: adversarial → la elección de guardrail que vimos en la
   strategy lattice.
2. Tres backends bindeados a roles. NO son tres instancias del mismo
   modelo — son tres familias distintas. Esa es la pieza que hace que
   adversarial funcione (recordá: distinto RLHF = distintos blind spots).
3. claude-cli como primary_reasoner (Claude Code, calidad alta de
   reasoning estructurado).
4. copilot-cli como research_coder (GitHub Copilot — calidad alta de
   research técnico con tools).
5. codex-cli como adversary_reasoner — y fijate que CUMPLE DOS roles
   (judge + utility). Eso es válido y económico — un mismo backend puede
   cubrir varios roles si las cargas no chocan.
6. max_iterations: 10 — presupuesto duro. Si no convergió a 10, se
   detiene.
7. allowed_tools: tools reales, no mockeados. WebSearch, WebFetch, Read,
   Bash, Glob, Grep — el agente realmente busca en la web y lee archivos
   locales.

La frase de cierre — "Critic and judge are deliberately different from
the researcher" — repetila lentamente. Es el corazón del approach
adversarial.
-->

---
<!-- TIMING: 1 min — slide de dry-run, después 2 min de demo en terminal -->

## Dry-run first — validate without spending tokens

```bash
# Validate config wiring, provider health, and tool capabilities — no backend calls
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex.yaml \
  --dry-run
```

Output confirms:
- All backend adapters resolve and are reachable
- Strategy is valid for the declared role topology
- Tool capability registry is satisfied
- Sandbox policy is coherent

Then run for real (this is the staged playback):

```bash
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex.yaml
```

<!--
NOTAS DEL ORADOR (slide 21 — dry-run):

PRESENTADOR: cambiá a la terminal y mostrá el playback grabado del run.
Mientras carga, comentá las líneas del log de iteración — hipótesis,
score, decisiones KEEP/DISCARD apareciendo en tiempo real.

Por qué dry-run importa: sin él, un error de config (un backend no
disponible, un role no bindeado, un tool no clasificado) te lo enterás a
mitad de la corrida cuando ya gastaste tokens. El dry-run valida TODO el
wiring sin hacer una sola llamada a backend. Es 5 segundos de chequeo
para evitar 5 minutos de pérdida.

Lo que el dry-run confirma:
- Los adapters de backend resuelven y son alcanzables (provider health).
- La strategy es válida para la topología de roles declarada.
- El capability registry de tools está satisfecho (no hay tool no clasificado).
- La política del sandbox es coherente (no hay write boundaries que choquen).

Si el dry-run pasa, podés correr con --no-dry-run con confianza. Si falla,
el error te dice exactamente qué arreglar.
-->

---
<!-- _class: divider video-bg -->
<!-- TIMING: transición, 10 seg -->

## III · ADVERSARIAL

# Adversarial critique in action

### What the critic actually said — from the real run

<!--
NOTAS DEL ORADOR (slide 22 — divisor adversarial):

Transición corta. Avisá que lo que viene son citas LITERALES del judge en
una corrida real. No editadas, no parafraseadas. Si la audiencia tiene
escépticos, este es el momento donde tenés evidencia concreta de que
adversarial encuentra cosas reales.
-->

---
<!-- TIMING: 3 min — el slide más importante. Mostrá la crítica encontrando un error real, después mostrá que se arregló. -->

## The critic finds real errors

**Iteration 001** — Researcher (Copilot) delivers AWS service coverage findings. Score: **62.0**

The judge backend (GPT-5.4) reviews and raises:

> *"MiniStack section appears materially stale — API Gateway v1, Cognito, and KMS coverage are asserted without current primary source evidence."*

> *"Moto capabilities are mischaracterized — Lambda execution mode and IAM enforcement nuance are factually wrong."*

> *"Many fine-grained feature claims are overconfident relative to the cited evidence."*

**These are not style comments. They are factual challenges** — a different model, different training data, catching different errors.

The loop forces the next iteration to resolve these gaps or be discarded.

<!--
NOTAS DEL ORADOR (slide 23 — el crítico encuentra errores reales):

Este es el slide más importante de toda la sección de demo. Si la
audiencia se va a casa con UNA cosa, que sea esto: el adversarial
critique no es teatro — encuentra errores factuales.

Iteración 001: Copilot (researcher) entregó findings sobre cobertura de
AWS services en alternativas a LocalStack. Score 62. La calidad parecía
razonable a primera vista — pero un judge de otra familia (GPT-5.4) la
miró y encontró tres problemas duros.

Repasá las tres citas DESPACIO. Son literales del audit log.

1. "MiniStack section appears materially stale" — el critic identifica que
   los claims sobre API Gateway v1, Cognito, y KMS no tienen evidencia
   primaria actual. NO está diciendo "no me gusta cómo está escrito" —
   está diciendo "estos tres claims específicos no tienen fuente actual".

2. "Moto capabilities are mischaracterized" — el critic dice que el
   modo de ejecución de Lambda y el matiz de enforcement de IAM están
   FÁCTICAMENTE MAL. Factualmente. Chequeable.

3. "Overconfident relative to the cited evidence" — el critic señala que
   muchos claims fine-grained son más fuertes de lo que la evidencia
   sostiene. Es un problema de calibración.

El punto que tenés que martillar: estos NO son comentarios de estilo. NO
son "fixame el wording". Son desafíos factuales — modelo distinto, datos
de entrenamiento distintos, captura errores distintos.

El loop fuerza a la siguiente iteración a resolver estos gaps o a
descartar el claim. No hay "ignorá el feedback del critic". Es estructural.
-->

---
<!-- TIMING: 2 min — mostrá la tabla de score, llamá la atención al dip en iter 007 (una dimensión más dura) y al salto a 76.3 en 009. -->

<!-- _class: tight -->

## Score progression — convergence is measurable

Each bar is one iteration. Score = heuristic (40%) + LLM judge (60%).

| Iteration | Dimension | Score | Decision |
|---|---|---|---|
| 001 | AWS service coverage | **62.0** | KEEP |
| 002 | Community activity & bus factor | 63.0 | KEEP |
| 003 | Migration effort | 63.5 | KEEP |
| 004 | CI/CD integration | 63.5 | KEEP |
| 005 | IaC toolchain (Terraform/CDK/SAM) | **69.5** | KEEP |
| 006 | CloudFormation source verification | 68.0 | KEEP |
| 007 | Migration effort by team profile | 63.5 | KEEP *(harder dimension)* |
| 008 | API behavioral fidelity | 66.0 | KEEP |
| **009** | Migration effort (final) | **76.3** | KEEP |

> Iter 007 dipped because the critic flagged under-validated migration estimates.
> The loop forced a harder verification pass. Iter 009 resolved it — **+12.8 points** on the final dimension.

<!--
NOTAS DEL ORADOR (slide 24 — curva de score):

La forma de la curva importa más que los números. No es lineal — sube,
baja en iter 007, después salta. Esa NO-linealidad es la firma de
convergencia adversarial real, no de un modelo "haciendo lo que se le
pide".

Iter 001 a 006: subida progresiva. El sistema agrega dimensiones, el
score promedio crece.

Iter 007: dip a 63.5. Acá es donde tenés que detenerte. ¿Por qué bajó?
Porque el critic flagged "migration estimates under-validated" — los
números de esfuerzo de migración no estaban sosteniendos por evidencia
suficiente. El loop NO escondió eso para mantener una curva linda. Lo
registró y forzó la próxima iteración a ir más profundo.

Iter 009: salto a 76.3. Esa iteración resolvió el problema — +12.8
puntos sobre la dimensión específica que estaba mal sostenida. Eso es
convergencia real: bajaste cuando descubriste un problema, subiste cuando
lo resolviste.

Si la curva fuera monótona-creciente sin nunca bajar, eso sería SOSPECHOSO
— el modelo estaría escribiéndole al judge en vez de investigando. La
forma "subida, dip, salto" es saludable.

Score = 40% heurística + 60% judge. Repetí esa fórmula si te preguntan
qué significa el número.
-->

---
<!-- TIMING: 1 min — transición a mostrar los outputs -->

## From one corpus — three artifacts

The research loop runs **once**. The output style is a rendering decision, not a research decision.

```yaml
reporting:
  output_style: technical_doc   # default | paper | technical_doc | executive_brief | decision_memo
```

Re-render any past run without re-running research:

```bash
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex_paper.yaml \
  --synthesize   # skips research loop, only re-renders
```

**Same data. Same citations. Different artifact.**

<!--
NOTAS DEL ORADOR (slide 25 — un corpus, tres artefactos):

La separación clave: el LOOP DE INVESTIGACIÓN corre una vez. Lo que
cambia entre artifactos es el RENDERING, no el research. Misma data,
mismas citas, distinto formato de salida.

Eso te permite re-renderizar runs viejos a nuevos formatos sin volver a
gastar en backend calls. El flag --synthesize saltea el loop completo y
solo re-emite el reporte. Si descubriste hace un mes algo importante y
ahora necesitás presentarlo en formato paper para stakeholders, son 5
segundos, no 5 minutos de re-investigación.

Los cinco styles disponibles: default, paper, technical_doc,
executive_brief, decision_memo. Vamos a ver tres en detalle (default,
paper, technical_doc). Los otros dos son variantes — executive_brief es
versión corta de decision_memo orientada a C-level.
-->

---
<!-- TIMING: 1.5 min — mostrá el reporte raw en el browser -->

## Output: `default` — for internal exploration

![bg right:52% fit](localstack-alternatives/images/raw.png)

Quick narrative synthesis, sectioned by dimension, embedded comparison tables.

**Use when:**
- Exploring a topic
- Sharing internal findings
- Fast iteration before committing to a format

**Closest analog:** a thorough Notion research page

<!--
NOTAS DEL ORADOR (slide 26 — output: default):

Este es el formato más liviano. Síntesis narrativa, secciones por
dimensión, tablas comparativas embebidas. Lo más cercano que vas a tener
a una "página de Notion bien laburada".

Cuándo usarlo: exploración interna, compartir findings dentro del equipo,
iteración rápida antes de decidir el formato final. Es el default por una
razón — es el menos opinado, no asume audiencia.

NO usarlo para: stakeholders externos, decisiones formales, documentos
que se van a citar después.

Mostrá el browser tab si lo tenés abierto. Pasá rápido, no es el money
slide — los siguientes dos sí.
-->

---
<!-- TIMING: 1.5 min — mostrá el reporte paper en el browser -->

## Output: `paper` — for stakeholders and external review

![bg right:52% fit](localstack-alternatives/images/paper.png)

Abstract, methodology section, evidence-backed claims, deterministic `## References` built from `citations.json`.

**Use when:**
- Writing for external review
- Stakeholder reports where evidence provenance matters
- Anything that will be cited downstream

**Closest analog:** a literature review or RFC with bibliography

<!--
NOTAS DEL ORADOR (slide 27 — output: paper):

Acá el formato cambia drásticamente. Estructura tipo paper académico:
abstract arriba, sección de methodology que documenta cómo se llegó a las
conclusiones, claims con evidencia explícita, y al final una sección
References generada DETERMINÍSTICAMENTE desde citations.json.

"Determinísticamente" es la palabra clave. La bibliografía no es una
sugerencia del LLM — es construida a partir del archivo estructurado de
citas que el sistema mantuvo durante todo el run. Si una cita no está
en citations.json, no puede aparecer en el output. Eso te da garantías
sobre provenance que un LLM solo no puede dar.

Cuándo usarlo: stakeholders externos, reportes donde el provenance
importa más que la prosa, cualquier cosa que vaya a ser citada por otros
documentos downstream. Audiencias técnicas-formales lo prefieren porque
saben dónde buscar la evidencia.

Mostrá la página References en el browser. Es la prueba visible de la
estructura.
-->

---
<!-- TIMING: 1.5 min — mostrá el reporte technical en el browser. Este es el money slide para audiencias de ingeniería. -->

## Output: `technical_doc` — for engineering decisions

![bg right:52% fit](localstack-alternatives/images/technical.png)

Comparison tables, decision matrix, recommendation upfront, structured pros/cons per alternative.

**Use when:**
- Architecture Decision Records (ADRs)
- Vendor / tool evaluation
- Decision memos for engineering teams

**Closest analog:** an RFC or ADR with a verdict

<!--
NOTAS DEL ORADOR (slide 28 — output: technical_doc):

Este es EL money slide para audiencias de ingeniería. Tablas
comparativas, matriz de decisión, recomendación arriba (no enterrada al
final), pros/cons estructurados por alternativa.

La estructura es la de un ADR (Architecture Decision Record) o un RFC
con veredicto. Empieza por la conclusión — "recomendamos X porque Y" —
y después justifica. Es la forma que tu equipo de ingeniería ya conoce.

Cuándo usarlo: ADRs, evaluación de vendors o tools, decision memos para
equipos técnicos. Cualquier momento donde el reader quiere saber qué
hacer ANTES de saber por qué.

Mostrá la decision matrix en el browser. Si tenés tiempo, hacé scroll a
la sección de pros/cons — es la parte donde el formato se gana el sueldo.

Si la audiencia es técnica, este es el formato que más les va a interesar.
-->

---
<!-- TIMING: 1.5 min — mostrá el directorio de output en la terminal. Apuntá a rerun.sh. -->

<!-- _class: tight -->

## Every run is fully replayable

```
output/localstack_alternatives_copilot_codex/
├── run.log                  ← human-readable operational log
├── audit_trail.jsonl        ← append-only structured trail: steps, tool calls, denials, policy events
├── effective_config.json    ← full normalized config snapshot at run time
├── tool_trace.json          ← per-tool args + truncated outputs
├── prompt_snapshot.json     ← exact prompts sent at run start
├── rerun.sh                 ← runnable exact-replay script
├── iterations/
│   ├── iter_001.md          ← hypothesis + findings + critique + score
│   └── iter_009.md
└── report.html              ← rendered output
```

`rerun.sh` is not documentation — it's an executable that reconstructs the exact run.
No "it worked on my machine."

<!--
NOTAS DEL ORADOR (slide 29 — replayable):

Recorré el árbol de archivos despacio. Cada uno tiene un propósito
auditable:

- run.log: log operacional human-readable. Para mirar rápido qué pasó.
- audit_trail.jsonl: trail estructurado append-only. Cada paso, cada
  tool call, cada denial, cada decisión de policy. ESTE es el archivo
  forense. Si querés saber qué decidió el sistema y por qué, lo abrís
  con jq.
- effective_config.json: snapshot completo del config NORMALIZADO al
  arrancar el run. No es el YAML original — es el YAML después de
  resolver defaults, expandir referencias, validar schema. Eso te
  permite reproducir aunque cambien los defaults del código mañana.
- tool_trace.json: argumentos de cada tool call y output truncado. Para
  debugear qué buscó el agente y qué encontró.
- prompt_snapshot.json: los prompts EXACTOS enviados al arranque. Si el
  sistema cambia los prompts por defecto en una versión futura, este
  archivo te permite reconstruir con los originales.
- rerun.sh: NO es documentación — es ejecutable. Lo corrés y reconstruye
  el run idéntico. No hay "funcionaba en mi máquina".
- iterations/: una carpeta por iteración con hipótesis, findings,
  crítica y score. Si querés ver cómo evolucionó el pensamiento del
  sistema, lo lees iteración por iteración.
- report.html: el output renderizado en el style elegido.

La parte que más impresiona a auditores: rerun.sh ejecutable. Ningún
sistema de research convencional te garantiza eso.
-->

---
<!-- TIMING: 1 min — terminal del audit trail: cat ... | python3 -m json.tool | head -40 -->

<!-- _class: tight -->

## Trust + certainty — every claim is classified

Every entry in `citations.json` and `claims.json` carries a `trust_class`:

| Class | Meaning |
|---|---|
| `untrusted_web_content` | URL citation from live web search — treat as external, unverified |
| `user_provided_source_material` | Operator-provided input files — trusted by the operator |
| `inferred_claim` | LLM-synthesised without a direct citation — explicitly flagged |

Plus PRISMA-style evidence logs:
- `search_log.json` — what was searched, when, from which backend
- `screening_log.json` — what was included or excluded, and why
- `certainty_tables.json` — first-pass certainty score per claim

> Readers know **exactly how strong each conclusion is** before acting on it.

<!--
NOTAS DEL ORADOR (slide 30 — trust + certainty):

Cada claim que el sistema emite carga una clasificación de trust. Es la
forma de ser explícitos sobre cuán fuerte es cada conclusión. Hay tres
clases:

1. untrusted_web_content: cita de URL que viene de búsqueda web en vivo.
   Tratar como externa y no verificada hasta que un humano la valide.
   Default conservative — el sistema NO confía en una URL solo porque
   apareció en results.

2. user_provided_source_material: archivos de input que el operador
   subió. El sistema confía en estos al nivel del operador. Si vos le
   subiste el doc, el sistema asume que vos lo verificaste.

3. inferred_claim: claim sintetizado por el LLM sin cita directa. Esto
   está EXPLÍCITAMENTE flagged. NO se esconde como "afirmación general".
   Si el sistema infiere algo sin fuente, te lo dice.

Más arriba todavía: hay logs estilo PRISMA (la metodología de revisiones
sistemáticas de medicina, adaptada acá).

- search_log: qué buscó, cuándo, desde qué backend.
- screening_log: qué se incluyó o se excluyó del corpus, y POR QUÉ.
- certainty_tables: score de certeza first-pass por claim.

Punto pedagógico: el sistema NO te dice "esto es verdad". Te dice "esto
es lo que encontré, esta es la fuerza de la evidencia, este es el path
de auditoría". El reader sabe qué tan fuerte es cada conclusión ANTES
de actuar sobre ella. Eso es honestidad estructural.
-->

---
<!-- TIMING: 30 seg — costo. Cortito. Números del run real. -->

<!-- _class: tight -->

## This run

Real execution data from the `localstack_alternatives_copilot_codex` run:

| Metric | Value |
|---|---|
| Backends | `claude-cli` (Claude Sonnet) · `copilot-cli` (Claude Sonnet 4.6) · `codex-cli` (GPT-5.4) |
| Strategy | `adversarial` — researcher + critic + arbitrator |
| Dimensions covered | **8 of 8** |
| Iterations | **9** (+ compression at iter 4) |
| Best score reached | **76.3 / 100** |
| Output formats generated | 3 (`default`, `paper`, `technical_doc`) |
| Execution cost | **$0.00** — all CLI adapters, flat-rate subscriptions |

> CLI adapters reuse existing Claude Pro / Copilot / Codex subscriptions — **flat cost, not per-token**.
> API adapters (for CI/unattended runs) bill per-token. Choose based on context.

<!--
NOTAS DEL ORADOR (slide 31 — this run):

Métricas del run real. Pasalo rápido (es solo medio minuto), pero
remarcá dos cosas:

1. Cost: $0.00. Eso NO es magia — es la elección de adapters CLI sobre
   adapters API. Los CLI adapters reusan tus suscripciones Claude Pro /
   Copilot / Codex que ya pagás como flat rate. Costo marginal por run:
   cero. Si tu equipo ya tiene esas suscripciones, podés correr esto
   ilimitado sin preocuparte por costos por token.

2. La caveat importante: para CI/CD o runs unattended, los CLI adapters
   no sirven (necesitan login interactivo). Para esos casos, usás los
   API adapters y se cobra por token. La elección depende del contexto
   — interactivo y exploratorio: CLI. Automated y producción: API.

8 de 8 dimensiones cubiertas, 9 iteraciones (+ 1 compresión en iter 4),
score final 76.3 sobre 100. Tres formatos de output generados. Eso es
lo que viste durante todo el demo, condensado en una tabla.
-->

---
<!-- TIMING: 1 min — takeaways como conclusiones -->

## What you just saw

1. Two different model families **argued about LocalStack alternatives** for 9 iterations
2. The critic (GPT-5.4) caught real factual errors in the researcher's (Copilot) output
3. The loop forced resolution — the final score improved **+14.3 points** from iteration 1 to 9
4. Three publication-ready artifacts were produced from **one research corpus**
5. Every claim carries a `trust_class` — the system is honest about what it doesn't know
6. The full run is **exactly reproducible** via `rerun.sh`

> **The adversarial loop isn't about being clever. It's about the same engineering principle
> as code review: a second set of eyes with different priors catches different bugs.**

<!--
NOTAS DEL ORADOR (slide 32 — takeaways):

Los 6 puntos son los takeaways operacionales. Repasalos en orden, sin
agregar contenido nuevo — son recordatorios de lo que la audiencia
acaba de ver.

Pero el blockquote del final es donde tenés que aterrizar el avión. La
analogía con code review es DELIBERADA: el adversarial loop NO es un
truco clever de AI, es el mismo principio de ingeniería que code review.
Un segundo par de ojos con priors distintos atrapa bugs distintos.

Esa analogía hace que la audiencia "se lleve" el concepto sin
necesidad de recordar los 11 patrones por nombre. Si entienden code
review, entienden por qué adversarial funciona. Esa es la victoria
pedagógica del slide.

Si te queda tiempo, podés ofrecer la última observación: "los humanos
que hacen code review hace décadas — esto solo aplica el mismo principio
a la generación de research, en vez de aplicarlo a código".
-->

---
<!-- _class: tighter spec video-bg -->
<!-- _paginate: false -->

## Multi-LLM Adversarial Convergence Framework

| | |
|---|---|
| **Version** | `0.x` — research preview |
| **Repo** | `github.com/josefigueredo/multillm-adversarial-convergence` |
| **License** | See repository |
| **Patterns** | 11 — Engine (3) · Topology (5) · Guardrails (3) |
| **Backends** | Claude · Copilot · Codex · Gemini · API + CLI adapters |
| **Outputs** | `default` · `paper` · `technical_doc` · `executive_brief` · `decision_memo` |

### Try it

```bash
uv sync
CONFIG=configs/research/localstack_alternatives_copilot_codex.yaml
uv run python -m src.cli research --config "$CONFIG" --dry-run    # validate
uv run python -m src.cli research --config "$CONFIG"              # run
```

Copy a template for your own topic: `configs/research/_template.yaml` · Read on: [`docs/research.md`](../research.md) · [`docs/design/agentic-design-patterns.md`](../design/agentic-design-patterns.md) · [`AGENTS.md`](../../AGENTS.md)

<!--
NOTAS DEL ORADOR (slide 33 — try it / spec card):

Cierre. Tres comandos para que la audiencia arranque por su cuenta:
uv sync, dry-run con su propio config, y run real.

El template _template.yaml está pensado para que copien y modifiquen —
no necesitan empezar de cero. Cualquier topic que se les ocurra (su
propia decisión técnica, su propia evaluación de tools, su propia
investigación) entra ahí.

Si tu charla tuvo Q&A, este es el momento para abrir preguntas. Las
referencias en el footer del slide te dan tres lugares donde mandar a
quien quiera profundizar:

- docs/research.md: cómo se usa el sistema en detalle.
- docs/design/agentic-design-patterns.md: el reference doc del repo
  con los 11 patrones mapeados a archivos del código.
- AGENTS.md: las convenciones para que un agente trabaje en este repo.

Si alguien te pregunta "¿lo puedo usar para X?" — la respuesta default
es "probablemente sí, copiá el template y abrí un issue si te trabás".
La barrera de entrada está baja a propósito.
-->

<!--
Render this deck:

  # HTML (best for screen recording)
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged_pro.md --html -o docs/showcase/demo_merged_pro.html

  # PowerPoint (notas de speaker no se exportan a PPTX speaker notes — son visibles solo en HTML presenter view)
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged_pro.md -o docs/showcase/demo_merged_pro.pptx

  # PDF con notas como anotaciones
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged_pro.md --pdf --pdf-notes -o docs/showcase/demo_merged_pro.pdf

  # Notas exportadas a archivo de texto
  npx @marp-team/marp-cli docs/showcase/demo_merged_pro.md --notes -o docs/showcase/demo_merged_pro_notes.txt
-->
