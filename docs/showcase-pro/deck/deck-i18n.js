/* deck-i18n.js — translation dictionary for the deck.
 *
 * English is the source of truth (it lives in deck.html itself).
 * This file provides ES overrides keyed by the data-i18n attribute on
 * each translatable element. Missing keys fall back to English silently.
 *
 * IMPORTANT: nested data-i18n elements (e.g. <blockquote data-i18n>
 * wrapping a <p data-i18n>) are processed outer-first. If the outer key
 * is translated, the inner annotation gets detached (its DOM node is
 * replaced). So when the outer's Spanish translation is provided, it
 * must include the same inline markup (e.g. <p><em>...</em></p>) so
 * styling is preserved end-to-end. When the outer has no Spanish key,
 * the inner's Spanish (if any) is applied normally.
 *
 * Convention used here:
 *   - For `quote-N` (blockquote taglines), the ES value wraps the text
 *     in <p><em>...</em></p> to match the source markup.
 *   - For `bq.N` (body-callout blockquotes), no ES is provided — the
 *     inner <p data-i18n="p.X"> carries the translation.
 *   - For `p.X` that duplicate a `quote-N` lead, ES is omitted (the
 *     blockquote's `quote-N` Spanish renders first and the inner <p>
 *     gets detached harmlessly).
 *
 * To add a new translatable string:
 *   1. Add data-i18n="my-key" to the element in deck.html
 *   2. Add "my-key": "Traducción" to the es block below
 */
window.DECK_I18N = {
  es: {
    // ── shared chrome ─────────────────────────────────────────────
    "header": "MULTI-LLM ADVERSARIAL CONVERGENCE",
    "header.strat": "MULTI-LLM ADVERSARIAL CONVERGENCE · ESTRATEGIAS",
    "footer": "github.com/josefigueredo/multillm-adversarial-convergence",

    // ── section dividers ─────────────────────────────────────────
    "i--strategies": "I · ESTRATEGIAS",
    "execution-strategies-section": "Estrategias de ejecución",
    "one-config-field-six-shapes": "Un campo de config · Seis topologías de backend fundamentalmente distintas",
    "divider-tagline-1": "<em>Elegí tu topología antes que tus patrones.</em>",

    "ii--patterns": "II · PATRONES",
    "agentic-design-patterns": "Patrones de diseño agéntico",
    "engine--topology--guardrails": "Motor · Topología · Guardrails",
    "divider-tagline-2": "<em>11 patrones nombrados de la literatura de investigación — cada uno citado, cada uno reemplazable.</em>",

    "iii--demo": "III · DEMO",
    "demo": "Demo",
    "aws-api-gateway--a-real-architecture-question": "AWS API Gateway — una pregunta de arquitectura real",
    "divider-tagline-3": "<em>&quot;¿Qué opción de AWS API Gateway debería elegir una plataforma enterprise para APIs REST y WebSocket — y cuándo no debería migrar?&quot;</em>",

    "iv--adversarial": "IV · ADVERSARIAL",
    "adversarial-critique-in-action": "Crítica adversarial en acción",
    "what-the-critic-actually-said--from-the-real-run": "Lo que el crítico realmente dijo — del run real",

    // ── slide 1 — intro ──────────────────────────────────────────
    "multi-llm-adversarial-convergence-framework": "Framework Multi-LLM de Convergencia Adversarial",
    "multi-llm-adversarial-convergence-framework-1": "Framework Multi-LLM de Convergencia Adversarial",
    "make-competing-llms-argue-until-they-converge-on-the-best-answer": "Un framework para hacer que LLMs en competencia discutan hasta converger en la mejor respuesta",
    "p.1": "<strong>Demo grabada</strong> — esto es un run real reproducido a velocidad.<br />\nTodos los artefactos mostrados son outputs reales de la ejecución.",

    // ── slide 2 — the problem ───────────────────────────────────
    "the-problem": "El problema",
    "p.2": "La investigación con un solo modelo es <strong>no determinística y no verificable</strong>.<br />\nUn LLM, una pasada, una perspectiva.",
    "p.3": "No podés saber qué le faltó ver, qué inventó con confianza, ni si un modelo distinto hubiera llegado a la misma conclusión.",
    "p.4": "<strong>La respuesta de este framework:</strong>",
    "li.1": "Correr múltiples backends sobre el mismo tema",
    "li.2": "Hacer que se <strong>puntúen, critiquen y discutan entre sí</strong>",
    "li.3": "Conservar sólo lo que sobrevive a la revisión adversarial",
    "li.4": "Emitir un evidence trail completo para auditar cada claim",

    // ── slide 3 — origin (Karpathy) ──────────────────────────────
    "origin-karpathys-autoresearch": "Origen: el <code>autoresearch</code> de Karpathy",
    "p.5": "El loop no es original. <a href=\"https://github.com/karpathy/autoresearch\">El <code>autoresearch</code> de Andrej Karpathy</a> corre:",
    "quote-1": "<p><em>modificás código → entrenás 5 min en GPU → medís loss → keep o revert</em></p>",
    "p.7": "El insight: <strong>esta forma se aplica a cualquier cosa que puedas puntuar</strong>.",
    "p.8": "Mismo loop. Distinto sustrato: <strong>conocimiento en vez de pesos</strong>.",
    "th.1": "<code>autoresearch</code> de Karpathy",
    "th.2": "Este framework",
    "td.1": "Entrenamiento en GPU",
    "td.2": "Llamada a backend LLM",
    "td.3": "Loss function",
    "td.4": "Heurística 40% + judge LLM 60%",
    "td.5": "Pesos de la red neuronal",
    "td.6": "Corpus de conocimiento",
    "td.7": "~5 min por iteración",
    "td.8": "Una llamada de backend por iteración",
    "td.9": "Para cuando el loss se estanca",
    "td.10": "Para con <code>max_iterations</code> o <code>target_dimensions_total</code>",

    // ── slide 4 — the loop ───────────────────────────────────────
    "the-loop": "El loop",

    // ── slide 5 — strategies divider (above)

    // ── slide 6 — strategies overview ────────────────────────────
    "p.10": "<em>Un campo de config. Seis formas fundamentalmente distintas de cablear backends.</em>",
    "th.3": "Estrategia",
    "th.4": "Cableado",
    "th.5": "Costo",
    "th.6": "Min backends",
    "td.11": "Un backend para todo",
    "td.14": "2 backends investigan en paralelo, un juez distinto",
    "td.17": "Todos los backends independientes, gana el mejor puntaje",
    "td.20": "Backend barato draftea, uno preciso refina",
    "td.23": "Rutea cada dimensión al backend que mejor encaja",
    "td.26": "Investigación + crítica + adjudicación",

    // ── slides 7-12 — strategy detail (with quote-N tagline wrappers)
    "strategy-single": "single",
    "strategy-ensemble": "ensemble",
    "strategy-parallel": "parallel",
    "strategy-serial": "serial",
    "strategy-specialist": "specialist",
    "strategy-adversarial": "adversarial",
    "quote-2": "<p><em>Un solo backend juega todos los roles — hipótesis, investigación, judge, utility, síntesis.</em></p>",
    "quote-3": "<p><em>Dos backends investigan la misma dimensión en paralelo; un tercero — de familia distinta — juzga cuál respuesta es mejor.</em></p>",
    "quote-4": "<p><em>Todos los backends investigan independientemente; el que tiene mejor score compuesto gana la iteración.</em></p>",
    "quote-5": "<p><em>Un backend barato genera un draft amplio; uno preciso lo refina — perfil de costo progresivo.</em></p>",
    "quote-6": "<p><em>Cada dimensión se rutea al backend cuya persona se ajusta mejor a la expertise requerida.</em></p>",
    "quote-7": "<p><em>El investigador produce, el crítico marca debilidades, el árbitro decide — tres roles, tres familias de modelos.</em></p>",

    // ── slide 14 — why patterns matter ───────────────────────────
    "why-these-patterns-matter": "Por qué importan estos patrones",
    "p.17": "Este codebase <strong>no es una colección de hacks</strong>.",
    "li.5": "<strong>Reemplazabilidad</strong> — cuando un patrón tiene nombre, intercambiar la implementación es mecánico",
    "li.6": "<strong>Defensibilidad</strong> — el code review puede preguntar <em>&quot;¿esto es Evaluator-Optimizer o Reflection?&quot;</em> en vez de <em>&quot;¿esto está bien?&quot;</em>",
    "li.7": "<strong>Onboarding</strong> — los contribuidores nuevos reconocen formas; no tienen que reverse-engineerear la intención",
    "p.18": "11 patrones: <strong>motor</strong> (3) + <strong>topología</strong> (5) + <strong>guardrails</strong> (3).",

    // ── slides 15-25 — pattern slides (titles kept canonical) ──
    "1--evaluator-optimizer": "1 · Evaluator-Optimizer",
    "2--llm-as-judge": "2 · LLM-as-Judge",
    "3--reflection--self-compression": "3 · Reflection / Auto-compresión",
    "4--orchestrator--subagents": "4 · Orquestador / Subagentes",
    "5--multi-agent-role-topology": "5 · Topología multi-agente de roles",
    "6--routing--specialist-dispatch": "6 · Routing / Dispatch a especialista",
    "7--parallelization-ensemble": "7 · Paralelización (Ensemble)",
    "8--prompt-chaining-serial": "8 · Encadenamiento de prompts (Serial)",
    "9--adversarial-critique": "9 · Crítica adversarial",
    "10--tool-use--sandboxed-execution": "10 · Uso de herramientas + ejecución en sandbox",
    "11--human-in-the-loop-hitl": "11 · Human-in-the-Loop (HITL)",
    "quote-8":  "<p><em>El loop externo. Proponer, puntuar, keep o discard, repetir.</em></p>",
    "quote-9":  "<p><em>Un modelo distinto puntúa al candidato. Sin auto-evaluación.</em></p>",
    "quote-10": "<p><em>Cada N iteraciones: destila el corpus, descarta el ruido.</em></p>",
    "quote-11": "<p><em>Un único dueño del lifecycle. Muchos workers con contrato angosto.</em></p>",
    "quote-12": "<p><em>Configurá roles, no modelos. Intercambiá backends sin cambiar la lógica.</em></p>",
    "quote-13": "<p><em>Cada dimensión va al backend mejor adaptado para ella.</em></p>",
    "quote-14": "<p><em>Fan-out a todos los backends en paralelo. Merge vía judge.</em></p>",
    "quote-15": "<p><em>Los backends se turnan. Cada etapa recibe la salida completa de la anterior.</em></p>",
    "quote-16": "<p><em>Investigador · Crítico · Árbitro — entre distintas familias de modelos.</em></p>",
    "quote-17": "<p><em>El registro de capabilities es el equivalente agéntico de una política de IAM.</em></p>",
    "quote-18": "<p><em>Compuertas de transición de fase. El operador aprueba antes de acciones irreversibles.</em></p>",

    // ── slide 26 — composition (strategy lattice) ────────────────
    "how-they-compose--the-strategy-lattice": "Cómo se componen — la lattice de estrategias",
    "th.7": "Capa",
    "th.8": "Patrones",
    "th.9": "Preocupación",
    "td.29": "<strong>Motor</strong>",
    "td.31": "Lo que hace que una iteración tenga sentido",
    "td.32": "<strong>Topología</strong>",
    "td.34": "Cómo se cablean y dispatchan los backends",
    "td.35": "<strong>Guardrails</strong>",
    "td.37": "Lo que evita que el agente haga lo incorrecto",
    "p.52": "<strong>Una estrategia configurada es una tupla sobre las capas.</strong> Run demo = <code>Adversarial Critique</code> (guardrail) sobre <code>Serial Chaining</code> (topología) usando <code>Evaluator-Optimizer + LLM-as-Judge</code> (motor), con <code>Sandbox</code> siempre activo.",

    // ── slides 28-30 — demo ──────────────────────────────────────
    "the-config--three-backends-adversarial-strategy": "La config — tres backends, estrategia adversarial",
    "p.53": "El investigador y el crítico están deliberadamente separados. El crítico es también el judge, así cada dimensión se revisa desde una familia distinta de modelos.",
    "dry-run-first--validate-without-spending-tokens": "Dry-run primero — validá sin gastar tokens",
    "p.54": "El output confirma:",
    "li.8": "Todos los adaptadores de backend resuelven y responden un preflight chico de <code>OK</code>",
    "li.9": "La estrategia es válida para la role topology declarada",
    "li.10": "El registro de capabilities de tools está satisfecho",
    "li.11": "La política de sandbox es coherente",
    "real-run--and-the-replay-dashboard": "Run real — y el dashboard de replay",
    "p.55": "Una vez que el dry-run pasa, corré de verdad. La ejecución completa streamea a <code>audit_trail.jsonl</code> — cada hipótesis, score y decisión KEEP/DISCARD por iteración es replayable.",

    // ── slides 32-33 — adversarial critique ──────────────────────
    "the-critic-finds-real-errors": "El crítico encuentra errores reales",
    "p.57": "<strong>Iteración 014</strong> — el rerun completa la dimensión de CORS después del crash de quota anterior. Score: <strong>101.5</strong>",
    "p.58": "El backend judge (GPT-5.4) conserva el resultado, pero todavía abre gaps de follow-up concretos:",
    "quote-19": "<p><em>&quot;Verificar el comportamiento de origen rechazado de HTTP API con una fuente primaria o un test reproducible.&quot;</em></p>",
    "quote-20": "<p><em>&quot;Re-chequear la interacción del authorizer de HTTP API cuando CORS está activado, especialmente el caso del $default-route.&quot;</em></p>",
    "quote-21": "<p><em>&quot;Separar comportamiento documentado del inferido o específico de implementación.&quot;</em></p>",
    "p.62": "<strong>Estos no son comentarios de estilo. Son riesgos de arquitectura</strong> — los status codes exactos, headers, paths del authorizer, y el comportamiento de IaC son la diferencia entre una API funcionando en el browser y un incidente en producción.",
    "p.63": "El loop preserva esos gaps en <code>discovered_gaps.json</code> para que una pasada posterior los pueda targetear directamente.",
    "score-progression--convergence-is-measurable": "Progresión del score — la convergencia es medible",
    "p.64": "Cada barra es una iteración. Score = heurística (40%) + judge LLM (60%).",
    "th.10": "Iteración",
    "th.11": "Dimensión",
    "th.12": "Score",
    "th.13": "Decisión",
    "p.65": "La iteración 009 fue una falla real: Claude se quedó sin tokens durante CORS.<br />\nResume preservó el corpus anterior, re-corrió sólo la dimensión faltante, y terminó con <strong>13 dimensiones keep</strong>.",

    // ── slide 34 — three artifacts ───────────────────────────────
    "from-one-corpus--three-artifacts": "De un solo corpus — tres artefactos",
    "p.66": "El loop de research corre <strong>una vez</strong>. El output style es una decisión de renderizado, no una decisión de research.",
    "p.67": "Re-renderizá cualquier run pasado sin re-correr la investigación:",
    "p.68": "<strong>Mismos datos. Mismas citas. Distinto artefacto.</strong>",

    // ── slides 35-37 — output styles ─────────────────────────────
    "output-default--for-internal-exploration": "Output: <code>default</code> — para exploración interna",
    "p.69": "Síntesis narrativa rápida para la decisión de AWS API Gateway: recomendaciones primero, luego dimensiones, caveats, y referencias.",
    "p.70": "<strong>Usalo cuando:</strong>",
    "li.12": "Compartís el run con ingenieros durante discovery",
    "li.13": "Escaneás trade-offs REST vs HTTP vs WebSocket",
    "li.14": "Iteración rápida antes de comprometerte a un memo formal",
    "p.71": "<strong>Analog más cercano:</strong> una página de research detallada en Notion",
    "output-paper--for-stakeholders-and-external-review": "Output: <code>paper</code> — para stakeholders y revisión externa",
    "p.72": "Abstract, sección de methodology, claims con evidencia, y referencias determinísticas construidas desde el mismo corpus de AWS.",
    "p.73": "<strong>Usalo cuando:</strong>",
    "li.15": "Escribís para revisión externa",
    "li.16": "Reportes para stakeholders donde la proveniencia de la evidencia importa",
    "li.17": "Cualquier cosa que va a ser citada río abajo",
    "p.74": "<strong>Analog más cercano:</strong> una literature review o un RFC con bibliografía",
    "output-technical_doc--for-engineering-decisions": "Output: <code>technical_doc</code> — para decisiones de ingeniería",
    "p.75": "Tablas de comparación, matriz de decisión, recomendación arriba, y disqualifiers explícitos para REST API, HTTP API, y WebSocket API.",
    "p.76": "<strong>Usalo cuando:</strong>",
    "li.18": "Architecture Decision Records (ADRs)",
    "li.19": "Reviews de arquitectura de plataforma",
    "li.20": "Decision memos para equipos de ingeniería",
    "p.77": "<strong>Analog más cercano:</strong> un RFC o ADR con un veredicto",

    // ── slide 38 — replayable ────────────────────────────────────
    "every-run-is-fully-replayable": "Cada run es totalmente replayable",

    // ── slide 39 — trust & certainty ─────────────────────────────
    "trust--certainty--every-claim-is-classified": "Trust + certainty — cada claim está clasificado",
    "p.78": "Cada entrada en <code>citations.json</code> y <code>claims.json</code> tiene un <code>trust_class</code>:",
    "th.14": "Clase",
    "th.15": "Significado",
    "td.70": "Cita de URL desde web search en vivo — tratar como externo, no verificado",
    "td.71": "Archivos provistos por el operador — confiados por el operador",
    "td.72": "Sintetizado por el LLM sin cita directa — flagueado explícitamente",
    "p.79": "Más los logs de evidencia estilo PRISMA:",
    "li.21": "<code>search_log.json</code> — qué se buscó, cuándo, desde qué backend",
    "li.22": "<code>screening_log.json</code> — qué se incluyó o excluyó, y por qué",
    "li.23": "<code>certainty_tables.json</code> — score de certeza de primera pasada por claim",

    // ── slide 40 — this run ──────────────────────────────────────
    "this-run": "Este run",
    "p.81": "Datos reales de ejecución del run <code>aws_api_gateway_opus_sonnet_codex</code>:",
    "th.16": "Métrica",
    "th.17": "Valor",
    "td.73": "Backends",
    "td.74": "Estrategia",
    "td.75": "Dimensiones cubiertas",
    "td.77": "Iteraciones",
    "td.78": "<strong>14 intentos crudos</strong> → <strong>13 dimensiones keep</strong> después del rerun de CORS",
    "td.79": "Mejor score alcanzado",
    "td.80": "<strong>101.5</strong> score compuesto en el rerun de CORS",
    "td.81": "Formatos de output generados",
    "td.83": "Costo de ejecución",
    "td.84": "<strong>$0.00 trackeado</strong> para adaptadores CLI durante la pasada final de resume/síntesis",
    "p.82": "Los adaptadores CLI reusan suscripciones existentes de Claude Pro / Copilot / Codex — <strong>costo flat, no por token</strong>.<br />\nLos adaptadores API (para runs de CI/desatendidos) facturan por token. Elegí según el contexto.",

    // ── slide 41 — what you just saw ─────────────────────────────
    "what-you-just-saw": "Lo que acabás de ver",
    "li.24": "Dos familias distintas de modelos <strong>discutieron sobre arquitectura de AWS API Gateway</strong> a lo largo de 13 dimensiones keep",
    "li.25": "El crítico (GPT-5.4) encontró riesgos reales sin resolver en CORS, authorizers, pricing, y confianza en evidencia",
    "li.26": "El loop sobrevivió a una falla de quota: el intento malo de CORS se excluyó y la dimensión faltante se re-corrió",
    "p.83": "<strong>El loop adversarial no es sobre ser inteligente. Es sobre el mismo principio de ingeniería<br />\nque el code review: un segundo par de ojos con priors distintos atrapa bugs distintos.</strong>",

    // ── slide 42 — spec ──────────────────────────────────────────
    "try-it": "Probalo",
    "td.85": "<strong>Versión</strong>",
    "td.87": "<strong>Licencia</strong>",
    "td.88": "Ver repositorio",
    "td.89": "<strong>Patrones</strong>",
    "td.90": "11 — Motor (3) · Topología (5) · Guardrails (3)",
    "td.91": "<strong>Backends</strong>",
    "td.93": "<strong>Outputs</strong>"
  }
};
