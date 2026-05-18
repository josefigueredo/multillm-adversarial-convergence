/* index-i18n.js — translation dictionary + apply engine for the showcase
 * landing page. English is the source of truth (it lives in index.html).
 * This file provides ES overrides keyed by data-i18n. Missing keys fall
 * back to the original English content silently.
 *
 * Same engine model as deck-lang.js — two-pass walk with originals cache.
 * Exposes:
 *   window.INDEX_I18N        — dictionary
 *   window.applyIndexLang(l) — called from the inline IIFE in index.html
 */
(() => {
  window.INDEX_I18N = {
    es: {
      // ── topbar / nav ───────────────────────────────────────────────
      "brand.label": "◉ &nbsp;MUESTRA · <strong>Multi-LLM Adversarial Convergence</strong>",
      "nav.deck": "Slides Principales",
      "nav.glossary": "Glosario",

      // ── hero ──────────────────────────────────────────────────────
      "hero.eyebrow": "Índice de la Muestra",
      "hero.title": "Presentaciones, herramientas<br>y artefactos de referencia — <em>PRO</em>",
      "hero.lede": "Mismo contenido que la muestra estática, más la capa de sincronización de slides-template-pro. El presentador maneja todos los viewers conectados por WebSocket — cambios de slide, cambios de vista, saltos a términos del glosario.",

      // ── section I: presentations ──────────────────────────────────
      "sec.1.eyebrow": "I · Presentaciones",
      "sec.1.title": "Plataforma de slides",
      "card.deck.tag": "Slides",
      "card.deck.title": "Slides Principales",
      "card.deck.desc": "Intro · <strong>I·Estrategias</strong> (6 estilos de ejecución) · <strong>II·Patrones</strong> (11 patrones agénticos de diseño) · <strong>III·Demo</strong> (corrida real de AWS API Gateway) · <strong>IV·Adversarial</strong> (hallazgos del crítico + outputs).",

      // ── section II: interactive tools ─────────────────────────────
      "sec.2.eyebrow": "II · Herramientas Interactivas",
      "sec.2.title": "Datos en vivo y demos animadas",
      "card.simulator.tag": "Simulador",
      "card.simulator.count": "11 patrones",
      "card.simulator.title": "Simulador de Patrones",
      "card.simulator.desc": "Elegí cualquiera de los 11 patrones agénticos — evaluator-optimizer, ensemble, crítica adversarial, HITL y más — y recorré una ejecución realista de un solo hilo con transiciones de rol, timeline y output del contrato.",
      "card.dashboard.tag": "Tablero",
      "card.dashboard.title": "Tablero de Replay en Vivo",
      "card.dashboard.desc": "Recorré cada iteración de la corrida real <code style=\"font-family:JetBrains Mono,monospace;font-size:0.85em;color:#f5a524\">aws_api_gateway_opus_sonnet_codex</code>. Sparkline del score, grilla de dimensiones, máquina de estados, decisiones KEEP/DISCARD y bloque de costos.",
      "card.shell.tag": "Demo",
      "card.shell.title": "Demo del Shell",
      "card.shell.desc": "Reproducción animada del terminal en formato standalone. El mismo componente de terminal scripteado usado dentro del deck principal, corriendo independiente como artefacto compartible.",

      // ── section III: reference ────────────────────────────────────
      "sec.3.eyebrow": "III · Referencia",
      "sec.3.title": "Glosario de conceptos y marco de ingeniería",
      "card.glossary.tag": "Referencia",
      "card.glossary.title": "Glosario de Conceptos",
      "card.glossary.desc": "Explicaciones bilingües estáticas para todos los términos clave — convergencia adversarial, evaluator-optimizer, LLM-as-judge, clases de confianza, atomicidad, y más. Diseñado para audiencias técnicas y no técnicas.",
      "card.harness.tag": "Notas",
      "card.harness.title": "Marco de Ingeniería del Harness",
      "card.harness.desc": "Material de preparación del expositor — analogía con el SO (CPU:LLM, kernel:harness), stack de tres capas y las ocho responsabilidades de la capa harness. Sirve como apertura antes de la sección de patrones.",

      // ── section IV: showcase outputs ──────────────────────────────
      "sec.4.eyebrow": "IV · Salidas de la Muestra",
      "sec.4.title": "AWS API Gateway — un corpus, tres perfiles de renderizado",
      "card.default.title": "Crudo / Por Defecto",
      "card.default.desc": "Síntesis exploratoria — recomendaciones primero, después dimensiones, advertencias y referencias inline. Ideal para descubrimiento de ingeniería y consumo interno.",
      "card.paper.title": "Estilo Paper",
      "card.paper.desc": "Estructura de paper académico — abstract, metodología, discusión, y una sección de referencias determinística construida desde <code style=\"font-family:JetBrains Mono,monospace;font-size:0.85em;color:#22d3ee\">citations.json</code>. Para revisión de stakeholders.",
      "card.technical.title": "Documento Técnico",
      "card.technical.desc": "Formato tipo ADR — tablas comparativas, recomendación arriba, descalificadores y preguntas abiertas. El equivalente más cercano a un RFC o registro de decisión de arquitectura.",

      // ── shared ────────────────────────────────────────────────────
      "open": "Abrir →",

      // ── footer ────────────────────────────────────────────────────
      "footer.title": "MULTI-LLM ADVERSARIAL CONVERGENCE · ÍNDICE DE LA MUESTRA",
    },
  };

  // Cache of original (English) innerHTML for byte-perfect restore.
  const originals = new WeakMap();

  window.applyIndexLang = function applyIndexLang(next) {
    const dict = (window.INDEX_I18N && window.INDEX_I18N[next]) || {};
    document.documentElement.lang = next;

    const all = Array.from(document.querySelectorAll("[data-i18n]"));
    // Pass 1 — snapshot originals before mutating anything.
    all.forEach((el) => {
      if (!originals.has(el)) originals.set(el, el.innerHTML);
    });
    // Pass 2 — apply, with the "skip parent with annotated descendant"
    // rule so we don't clobber nested translations.
    all.forEach((el) => {
      const key = el.dataset.i18n;
      const hasOwnTranslation = dict[key] !== undefined;
      const hasAnnotatedDescendant = el.querySelector("[data-i18n]") !== null;
      if (!hasOwnTranslation && hasAnnotatedDescendant) return;
      el.innerHTML = hasOwnTranslation ? dict[key] : originals.get(el);
    });
  };
})();
