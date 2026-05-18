window.GLOSSARY_I18N = {
  es: {
    ui: {
      searchLabel: "Buscar concepto",
      clear: "Limpiar",
      staticData: "sin backend · datos estáticos",
      ready: "LISTO",
      emptyTitle: "Escribe un término o elige uno de la lista.",
      emptyBody: "La tarjeta mostrará una definición simple, una analogía de negocio, una analogía técnica, por qué importa y cómo se conecta con este proyecto.",
      hintFocus: "enfocar búsqueda",
      hintMove: "mover",
      hintOpen: "abrir seleccionado",
      hintClear: "limpiar",
      noMatch: "SIN RESULTADOS",
      noConcept: "No hay concepto seleccionado.",
      tryTerms: "Prueba términos como harness, agente, judge, contexto, sandbox, resume o cobertura de citas.",
      noResults: "No hay términos coincidentes. Prueba una palabra más general.",
      concept: "CONCEPTO",
      plain: "Definición simple",
      business: "Analogía de negocio",
      technical: "Analogía técnica",
      matters: "Por qué importa",
      project: "En este proyecto",
      related: "Términos relacionados",
      termsSingular: "término",
      termsPlural: "términos",
      placeholder: "Prueba: harness, juez, ventana de contexto, sandbox..."
    },
    filters: {
      All: "Todos",
      None: "Ninguno",
      "AI Basics": "Bases de IA",
      Backends: "Backends",
      Core: "Núcleo",
      Governance: "Gobernanza",
      "Harness Layers": "Capas del harness",
      "IT Basics": "Bases de TI",
      Memory: "Memoria",
      Output: "Salida",
      Patterns: "Patrones",
      Products: "Productos",
      Reliability: "Confiabilidad",
      Research: "Investigación",
      Trust: "Confianza",
      Action: "Acción"
    },
    terms: {
      "Agent Harness": {
        term: "Harness de agente",
        plain: "La capa de software alrededor de un LLM que le permite actuar, observar resultados, conservar estado, recuperarse de fallos y completar trabajo de varios pasos.",
        business: "Un analista fuerte necesita proceso: entrada de tareas, herramientas, aprobaciones, revisión, documentación y escalamiento. El harness es ese proceso alrededor del modelo.",
        technical: "El LLM es la CPU; el harness es el sistema operativo que gestiona memoria, herramientas, permisos, archivos y flujo de ejecución.",
        matters: "La mayor parte del valor en producción viene del sistema de control que rodea al modelo, no de una sola llamada al modelo.",
        project: "Este framework es un harness de investigación: coordina backends, críticas, scoring, compresión, resume, auditoría y generación de reportes."
      },
      "LLM": {
        term: "LLM",
        plain: "Un modelo que lee contexto y genera lenguaje.",
        business: "Un especialista con conocimiento que razona con el paquete de información que se le pone enfrente.",
        technical: "Un motor de inferencia casi sin estado: entran tokens de entrada y salen tokens de salida.",
        matters: "El modelo razona, pero no sabe por sí solo qué hacer después, qué herramientas son seguras o qué estado debe persistir.",
        project: "Claude, Codex, Copilot, Gemini y adaptadores API pueden conectarse al mismo loop de investigación."
      },
      "Agent": {
        term: "Agente",
        plain: "Un modelo más un harness que puede tomar acciones, observar resultados e iterar hacia un objetivo.",
        business: "No es solo un consultor que da consejos; es un operador que puede revisar evidencia, usar herramientas aprobadas y entregar un artefacto terminado.",
        technical: "Un loop de llamadas al modelo, llamadas a herramientas, actualizaciones de estado y condiciones de parada.",
        matters: "La agencia emerge de la combinación entre modelo y sistema de control.",
        project: "El agente de investigación ejecuta dimensiones, actualiza una base de conocimiento, acepta o rechaza iteraciones y sintetiza reportes."
      },
      "Context Window": {
        term: "Ventana de contexto",
        plain: "El conjunto limitado de tokens que el modelo puede ver durante una llamada.",
        business: "El paquete de reunión. Si la evidencia necesaria no está en el paquete, la persona probablemente no la use.",
        technical: "Memoria de trabajo rápida pero limitada, similar a RAM en la analogía de sistema operativo.",
        matters: "Las tareas largas fallan cuando el estado importante vive solo en la conversación y luego sale del contexto.",
        project: "El framework comprime la base de conocimiento y escribe archivos durables para continuar tras límites de contexto o reinicios."
      },
      "Runtime Charter": {
        term: "Carta de runtime",
        plain: "Las reglas compartidas que definen cómo se cumplen contratos, cómo persiste el estado, cómo funcionan presupuestos y cómo se supervisan agentes hijos.",
        business: "La política operativa de la empresa: aprobaciones, handoffs, escalamiento y registros sin importar el proyecto.",
        technical: "La semántica de ejecución debajo de la lógica específica del harness.",
        matters: "Permite ejecutar diferentes diseños de harness sobre el mismo sustrato para compararlos o reemplazarlos limpiamente.",
        project: "Config de ejecución, sandbox, retry/resume, preflight e atomicidad de iteraciones son preocupaciones de runtime charter."
      },
      "Backend Layer": {
        term: "Capa de backend",
        plain: "La infraestructura real y capacidades que el agente puede usar: modelos, shell, archivos, navegador, APIs, adaptadores y subagentes.",
        business: "Las herramientas y sistemas que los empleados tienen permitido usar para hacer el trabajo.",
        technical: "Adaptadores y superficies de ejecución que exponen capacidades al runtime.",
        matters: "El harness solo puede actuar a través de las capacidades que expone esta capa.",
        project: "El repo soporta adaptadores CLI y API como claude-cli, codex-cli, gemini-cli, copilot-cli y backends API."
      },
      "Natural-Language Harness": {
        term: "Harness en lenguaje natural",
        plain: "Un harness cuya lógica de control de alto nivel está escrita como lenguaje natural inspeccionable, no solo enterrada en código controlador.",
        business: "Un playbook operativo escrito que puede revisarse, editarse, entrenarse y compararse.",
        technical: "Un artefacto portable que describe roles, etapas, contratos, estado, adaptadores y modos de fallo.",
        matters: "Hace que el diseño del harness sea auditable, comparable y migrable entre runtimes.",
        project: "AGENTS.md, planes, configs y prompts ya funcionan como superficies de control portables alrededor del código."
      },
      "Tool Use": {
        term: "Uso de herramientas",
        plain: "El modelo solicita una capacidad externa, el harness la ejecuta y el resultado vuelve al siguiente paso.",
        business: "Pedirle a un analista que abra una hoja de cálculo, ejecute una consulta o verifique una fuente en vez de adivinar.",
        technical: "Llamadas a herramientas mediadas por adaptadores estables, normalmente protegidas por permisos y auditoría.",
        matters: "Las herramientas convierten lenguaje en acción verificada y recolección de evidencia.",
        project: "Las configs de research permiten herramientas como WebSearch, WebFetch, Read, Bash, Glob y Grep."
      },
      "MCP": {
        term: "MCP",
        plain: "Un protocolo para conectar modelos o agentes con herramientas y datos externos mediante una interfaz común.",
        business: "Un formato estándar de conectores para enchufar muchos sistemas al mismo proceso operativo.",
        technical: "Una interfaz de servidor de herramientas que expone recursos y acciones a un runtime de agente.",
        matters: "Reduce integración a medida y hace más portables las herramientas.",
        project: "La arquitectura trata las herramientas como adaptadores detrás del límite del harness."
      },
      "Sandbox": {
        term: "Sandbox",
        plain: "Un entorno controlado que limita lo que el agente puede leer, escribir, ejecutar o acceder.",
        business: "Dejar que un contratista trabaje dentro de un espacio aprobado en vez de darle toda la red de la empresa.",
        technical: "Límites de filesystem, comandos, red y permisos alrededor de la ejecución de herramientas.",
        matters: "Permite que los agentes actúen reduciendo el radio de daño.",
        project: "La política de sandbox limita escrituras y registra denegaciones o intenciones de escritura en la auditoría."
      },
      "Evaluator-Optimizer": {
        term: "Evaluador-Optimizador",
        plain: "Generar un candidato, evaluarlo, conservar el trabajo útil, descartar lo débil y repetir.",
        business: "Un ciclo de revisión: borrador, revisión, mejora, aceptar solo lo que cumple el nivel.",
        technical: "Un loop iterativo sobre propuestas con función de scoring y regla de aceptación.",
        matters: "Convierte una generación única en mejora medible.",
        project: "Cada iteración produce hallazgos, los puntúa y los fusiona en la base de conocimiento o los descarta."
      },
      "LLM-as-Judge": {
        term: "LLM como juez",
        plain: "Un modelo evalúa la respuesta de otro modelo usando una rúbrica.",
        business: "Un segundo revisor comprueba si el trabajo está completo, sustentado y es útil.",
        technical: "Una llamada separada produce scores, crítica estructurada y brechas.",
        matters: "Detecta problemas que el modelo productor puede no ver, especialmente si el juez viene de otra familia.",
        project: "El scorer combina heurísticas determinísticas con salida de juez para cobertura, calidad, novedad y gaps."
      },
      "Adversarial Critique": {
        term: "Crítica adversarial",
        plain: "Un modelo diferente busca fallos, evidencia faltante, razonamiento débil o afirmaciones demasiado seguras.",
        business: "Red team antes de aceptar una decisión.",
        technical: "Una etapa de crítica con backend o rol distinto para desafiar una salida candidata.",
        matters: "Modelos diferentes tienen puntos ciegos diferentes; el desacuerdo revela riesgos ocultos.",
        project: "La estrategia adversarial usa roles de investigador, crítico y juez sobre backends configurados."
      },
      "Prompt Chaining": {
        term: "Encadenamiento de prompts",
        plain: "Varias llamadas al modelo se ejecutan en secuencia y cada etapa recibe la salida anterior.",
        business: "Un trabajo que pasa por investigación, revisión, edición y aprobación.",
        technical: "Una secuencia dirigida de llamadas con artefactos de handoff entre etapas.",
        matters: "Divide trabajo complejo en contratos pequeños y hace visibles los fallos intermedios.",
        project: "Estrategias seriales y adversariales pasan investigación a crítica, scoring y síntesis."
      },
      "Parallelization": {
        term: "Paralelización",
        plain: "Varios backends trabajan al mismo tiempo en la misma tarea o tareas relacionadas, y luego se juzgan o fusionan los resultados.",
        business: "Varios analistas evalúan independientemente el mismo problema antes de comparar conclusiones.",
        technical: "Llamadas concurrentes a backends con agregación, selección o síntesis.",
        matters: "Aumenta diversidad de perspectivas y puede reducir tiempo calendario.",
        project: "El framework soporta estrategias ensemble y paralelas desde la capa de estrategia."
      },
      "Role Topology": {
        term: "Topología de roles",
        plain: "El mapeo de responsabilidades como investigador, crítico, juez, utility o sintetizador a backends específicos.",
        business: "Asignar personas a roles claros: analista, revisor, aprobador, editor.",
        technical: "Un grafo configurable de roles y reglas de despacho.",
        matters: "Permite cambiar familias de modelos sin reescribir la orquestación.",
        project: "Las configs asignan roles como primary, research, judge y utility a IDs de proveedores."
      },
      "Routing": {
        term: "Enrutamiento",
        plain: "El harness elige qué backend o rol debe manejar una tarea específica.",
        business: "Enviar temas legales a legal, datos a data y arquitectura a arquitectos.",
        technical: "Una función de despacho mapea dimensiones, personas o tipos de tarea a backends.",
        matters: "Distintos modelos y herramientas sirven mejor para distintos trabajos.",
        project: "La estrategia specialist puede enrutar dimensiones a personas configuradas o caer al backend primario."
      },
      "Reflection": {
        term: "Reflexión",
        plain: "El sistema revisa periódicamente su propio estado acumulado y lo destila a una forma más pequeña y limpia.",
        business: "Un equipo reescribe notas desordenadas en un memo de estado antes de seguir.",
        technical: "Context folding o compresión de corpus para mantener tareas largas dentro de límites de tokens.",
        matters: "Sin compresión, las corridas largas se vuelven caras, ruidosas o demasiado grandes.",
        project: "El loop de research comprime la base de conocimiento cada cierto número de iteraciones configuradas."
      },
      "Knowledge Base": {
        term: "Base de conocimiento",
        plain: "Los hallazgos aceptados acumulados durante la corrida.",
        business: "El dossier de investigación compartido que crece cuando el trabajo sobrevive revisión.",
        technical: "Un artefacto durable fusionado a través de iteraciones KEEP y usado después para síntesis.",
        matters: "Separa conocimiento aceptado de salida transitoria del modelo.",
        project: "Research escribe `knowledge_base.md` y lo usa para sintetizar reportes finales."
      },
      "Audit Trail": {
        term: "Registro de auditoría",
        plain: "Un registro append-only de lo que ocurrió durante la corrida.",
        business: "Un log de decisión que muestra qué se hizo, cuándo y por qué.",
        technical: "Eventos JSONL estructurados para iteraciones, scoring, gaps, política, rollback y ciclo de vida.",
        matters: "Hace que la corrida sea reproducible y depurable, no una caja negra.",
        project: "El framework escribe `audit_trail.jsonl` y lo usa para monitor y replay."
      },
      "Trust Class": {
        term: "Clase de confianza",
        plain: "Una etiqueta que indica qué tan bien fundamentada está una afirmación.",
        business: "Una etiqueta de confianza en una recomendación: con fuente, provista por operador o inferida.",
        technical: "Metadatos asociados a citas o claims, como contenido web no confiable o claim inferido.",
        matters: "Indica cuánta cautela usar antes de actuar.",
        project: "El showcase presenta trust classes para citas y claims en outputs de investigación."
      },
      "Citation Coverage": {
        term: "Cobertura de citas",
        plain: "Qué tanto de la síntesis final está respaldado por fuentes explícitas.",
        business: "Qué parte de la recomendación puede trazarse a evidencia y no solo a afirmaciones.",
        technical: "Una métrica sobre claims y referencias en artefactos generados.",
        matters: "Baja cobertura significa que el reporte puede sonar bien pero ser difícil de defender.",
        project: "El score bajo de AWS ocurrió porque la síntesis se corrompió y no tenía citas reales."
      },
      "Rubric": {
        term: "Rúbrica",
        plain: "Los criterios usados para juzgar si una salida es útil, sustentada y accionable.",
        business: "La tarjeta de evaluación usada en una revisión de decisión.",
        technical: "Una evaluación estructurada con dimensiones como calidad de evidencia, citas, incertidumbre y acción.",
        matters: "Convierte calidad subjetiva en señales inspeccionables.",
        project: "La finalización de research escribe `rubric.json` y resume la calidad del reporte."
      },
      "Resume": {
        term: "Reanudar",
        plain: "Continuar una corrida desde artefactos completados en vez de empezar desde cero.",
        business: "Retomar un proyecto desde el último hito completo después de una interrupción.",
        technical: "Cargar estado previo desde outputs, auditoría, archivos de iteración y sidecars.",
        matters: "Las corridas largas pueden fallar por cuotas, crashes o kills de proceso.",
        project: "El wrapper de retry detecta output existente y arranca con `--resume` cuando puede."
      },
      "Rollback": {
        term: "Rollback",
        plain: "Quitar efectos incompletos o corruptos de una iteración antes de reanudar.",
        business: "Deshacer una transacción a medias para que los libros cuadren antes de seguir.",
        technical: "Recuperación con sentinels que elimina filas, archivos y secciones parciales.",
        matters: "Sin rollback, un crash puede contaminar contexto y reportes futuros.",
        project: "La iteración 014 de AWS se revirtió manualmente después de que un banner de cuota entró en artefactos."
      },
      "Iteration Atomicity": {
        term: "Atomicidad de iteración",
        plain: "Una iteración se trata como transacción: o se escriben todos los archivos esperados o se limpian efectos parciales.",
        business: "Una transacción de base de datos aplicada a artefactos de investigación.",
        technical: "Un sentinel de in-progress marca el bloque de escritura para detectar y revertir trabajo incompleto.",
        matters: "Protege corridas largas contra estado corrupto después de kills de proceso.",
        project: "El framework escribe y limpia sentinels por iteración bajo `iterations/`."
      },
      "Backend Preflight": {
        term: "Preflight de backend",
        plain: "Una llamada mínima que pide a un backend CLI responder OK antes de iniciar trabajo costoso.",
        business: "Probar proyector, micrófono y credenciales antes de empezar la presentación.",
        technical: "Una sonda de bajo costo que detecta cuotas, login roto o salida CLI inválida temprano.",
        matters: "Los CLI cambian y fallan por versión o suscripción; preflight evita gastar una corrida en un backend muerto.",
        project: "La nueva implementación prueba backends CLI antes de research/refine/plan."
      },
      "CLI Adapter": {
        term: "Adaptador CLI",
        plain: "Un adaptador que habla con una herramienta local de línea de comandos en vez de una API hospedada.",
        business: "Usar una herramienta de escritorio ya licenciada en vez de un servicio cloud medido.",
        technical: "Un wrapper de subprocess que envía prompts a claude-cli, codex-cli, gemini-cli o copilot-cli.",
        matters: "Los CLI pueden reutilizar suscripciones, pero dependen de auth local, versión y cuotas.",
        project: "La corrida AWS usó Claude CLI para research/síntesis y Codex CLI para crítica/juez."
      },
      "API Adapter": {
        term: "Adaptador API",
        plain: "Un adaptador que llama a un proveedor de modelos por API.",
        business: "Un servicio gestionado con uso medido y mejor automatización.",
        technical: "Integración HTTP/API con modelo, tokens, errores y facturación explícitos.",
        matters: "Las APIs suelen ser mejores para CI y corridas desatendidas; los CLI pueden ser baratos para demos locales.",
        project: "El framework soporta codex-api, claude-api, gemini-api, litellm-api, bedrock-api y copilot-api."
      },
      "Quota": {
        term: "Cuota",
        plain: "Un límite del proveedor que impide más llamadas al modelo hasta que el uso se reinicie o vuelva capacidad.",
        business: "Un límite diario o de tarjeta para trabajo con modelos.",
        technical: "Un modo de fallo CLI/API que aparece como error, rate limit o banner de uso.",
        matters: "Los fallos de cuota pueden corromper artefactos si se confunden con salida del modelo.",
        project: "La síntesis AWS fallida contenía un banner de uso de Claude; ahora la lógica de salvage lo rechaza."
      },
      "Synthesis": {
        term: "Síntesis",
        plain: "El reporte final generado desde el corpus de investigación aceptado.",
        business: "El memo ejecutivo escrito después de completar el dossier de investigación.",
        technical: "Una llamada sobre base de conocimiento, citas, perfil de estilo y contrato de reporte.",
        matters: "Buenos artefactos de iteración no bastan; la síntesis debe conservar evidencia e incertidumbre.",
        project: "Research escribe `synthesis.md`, `report.html`, rúbricas y outputs por estilo."
      },
      "Output Style": {
        term: "Estilo de salida",
        plain: "La estructura y tono elegidos para el artefacto final.",
        business: "La misma investigación puede ser página interna, paper, memo técnico o resumen ejecutivo.",
        technical: "Un perfil de reporting que cambia convenciones de síntesis sin rerun de research.",
        matters: "Separa el trabajo de investigación del formato de publicación.",
        project: "Los estilos incluyen default, paper, technical_doc, executive_brief y decision_memo."
      },
      "Evidence": {
        term: "Evidencia",
        plain: "Fuentes, datos, ejemplos u observaciones que respaldan una afirmación.",
        business: "Los anexos detrás de una recomendación.",
        technical: "Citas, logs, referencias, artefactos y salidas de verificadores conectados a claims.",
        matters: "Sin evidencia, un reporte pulido es difícil de confiar.",
        project: "Las configs definen tipos de fuente preferidos, criterios de inclusión y expectativas de evidencia."
      },
      "Failure Taxonomy": {
        term: "Taxonomía de fallos",
        plain: "Categorías nombradas para qué salió mal y qué recuperación debe ejecutarse.",
        business: "Un playbook de soporte: auth, fuente faltante, timeout, datos malos, aprobación necesaria.",
        technical: "Diagnóstico estructurado que mapea fallos a retry, repair, skip, rollback o abort.",
        matters: "Los agentes necesitan caminos explícitos de recuperación, no errores vagos.",
        project: "El sistema registra diagnósticos como exit_code_mismatch y filas crash cuando la investigación vuelve vacía."
      },
      "Human-in-the-Loop": {
        term: "Humano en el loop",
        plain: "Una persona aprueba, rechaza o redirige al agente en transiciones importantes.",
        business: "Aprobación de manager antes de gastar dinero, desplegar cambios o publicar una decisión.",
        technical: "Gates de política que pausan ejecución hasta registrar una decisión humana.",
        matters: "Algunos pasos no deben delegarse completamente a automatización.",
        project: "HITL es parte de los patrones de guardrail y puede configurarse por fase."
      },
      "Research Dimension": {
        term: "Dimensión de investigación",
        plain: "Un ángulo enfocado de una pregunta de investigación más amplia.",
        business: "Un workstream dentro de una evaluación: costo, seguridad, migración, observabilidad, límites.",
        technical: "Un target configurado usado por el loop de hipótesis/iteración.",
        matters: "Hace explícita la cobertura y evita que la corrida se concentre solo en lo fácil.",
        project: "La config AWS tiene dimensiones de auth, CORS, cuotas, costo, deployment, WebSocket y más."
      },
      "Coverage": {
        term: "Cobertura",
        plain: "Qué tanto de la pregunta esperada fue abordado.",
        business: "Si la evaluación miró todos los criterios de decisión, no solo los obvios.",
        technical: "Componente de score informado por foco, evidencia, preguntas respondidas y longitud.",
        matters: "Un texto bien escrito puede fallar si ignora dimensiones clave.",
        project: "Los logs muestran sub-scores de cobertura junto con calidad y novedad."
      },
      "Novelty": {
        term: "Novedad",
        plain: "Cuánta información útil nueva agrega una iteración más allá de lo ya conocido.",
        business: "Evitar pagar otra reunión que repite las notas de la semana pasada.",
        technical: "Señal de scoring que premia contribución no duplicada al corpus.",
        matters: "Evita que corridas largas acumulen contenido repetido.",
        project: "Las configs pueden activar scoring mezclado con novedad y bonus de profundidad."
      },
      "Convergence": {
        term: "Convergencia",
        plain: "La corrida alcanza suficiente cobertura, score o dimensiones configuradas para detenerse y sintetizar.",
        business: "El equipo tiene suficiente evidencia revisada para tomar una decisión.",
        technical: "Condiciones de parada como max iterations, target dimensions o comportamiento de score.",
        matters: "Sin reglas de parada, el trabajo autónomo puede desviarse o gastar indefinidamente.",
        project: "Las corridas paran por límites configurados y luego generan artefactos de síntesis."
      },
      "RAG": {
        term: "RAG",
        plain: "Una técnica donde el sistema primero recupera documentos o datos relevantes y luego pide al modelo responder usando ese material.",
        business: "Antes de escribir un memo, el analista busca en el archivo y pone los documentos relevantes en la mesa.",
        technical: "La recuperación aporta contexto externo para que el modelo responda desde fuentes seleccionadas.",
        matters: "Reduce adivinanzas y hace las respuestas más trazables a evidencia.",
        project: "El loop de research hace una versión más amplia: junta fuentes, guarda hallazgos aceptados y sintetiza desde la base de conocimiento."
      },
      "Prompt": {
        term: "Prompt",
        plain: "La instrucción y contexto enviados al modelo para una llamada.",
        business: "La solicitud de trabajo más el paquete de antecedentes.",
        technical: "Tokens de entrada que condicionan la próxima salida del modelo.",
        matters: "Los modelos responden solo a lo que el harness les da en ese momento.",
        project: "Los prompts viven en `prompts/` y se combinan con configs, estado y artefactos."
      },
      "Tokens": {
        term: "Tokens",
        plain: "Piezas de texto que los modelos leen y escriben. Un token suele ser un fragmento de palabra.",
        business: "La unidad de facturación y capacidad para lectura y escritura del modelo.",
        technical: "Los modelos procesan texto como IDs de tokens; límites y precios suelen contarse en tokens.",
        matters: "Prompts y respuestas largas cuestan más y pueden llegar a límites.",
        project: "Los resúmenes reportan tokens de entrada/salida y la compresión controla su crecimiento."
      },
      "Embedding": {
        term: "Embedding",
        plain: "Una representación numérica de texto que ayuda a comparar significado.",
        business: "Una forma de archivar documentos por tema, no solo por palabras exactas.",
        technical: "Un vector denso usado para búsqueda por similitud, clustering o recuperación.",
        matters: "Los embeddings impulsan muchos sistemas de búsqueda y RAG.",
        project: "El showcase actual se basa más en corpus y citas, pero embeddings son técnica común de memoria."
      },
      "API": {
        term: "API",
        plain: "Una forma estructurada para que un software le pida a otro sistema hacer algo.",
        business: "Un mostrador de servicio con menú de solicitudes permitidas.",
        technical: "Un contrato de endpoints, entradas, salidas, autenticación y errores.",
        matters: "Las APIs permiten integrar sistemas sin que humanos hagan clic en pantallas.",
        project: "El framework puede usar adaptadores API y también investiga API Gateway como puerta de APIs empresariales."
      },
      "CLI": {
        term: "CLI",
        plain: "Una forma textual de ejecutar software escribiendo comandos.",
        business: "Una consola directa de operador en vez de una aplicación visual.",
        technical: "Comandos ejecutados en una shell que devuelven exit codes, stdout y stderr.",
        matters: "Muchas herramientas de desarrollo son más automatizables por CLI.",
        project: "El framework envuelve herramientas CLI como Claude Code y Codex como backends."
      },
      "Shell": {
        term: "Shell",
        plain: "El programa que recibe comandos escritos y los ejecuta en una computadora.",
        business: "El panel de control para operar archivos, programas y scripts.",
        technical: "Un intérprete de comandos como bash o zsh.",
        matters: "Agentes con shell pueden inspeccionar archivos, correr tests y ejecutar scripts determinísticos.",
        project: "La política de sandbox controla cuándo y dónde pueden correr comandos shell."
      },
      "JSON": {
        term: "JSON",
        plain: "Un formato de texto común para datos estructurados.",
        business: "Un formulario estandarizado con campos nombrados que el software puede leer.",
        technical: "Objetos, arrays, strings, números, booleanos y null codificados como texto.",
        matters: "Las salidas estructuradas son más fáciles de validar y reproducir que prosa libre.",
        project: "Auditorías, dashboards, rúbricas y sidecars se guardan como JSON o JSONL."
      },
      "YAML": {
        term: "YAML",
        plain: "Un formato legible por humanos usado frecuentemente para archivos de configuración.",
        business: "Una hoja de ajustes para decir cómo debe correr un sistema.",
        technical: "Datos de configuración por indentación y claves/valores.",
        matters: "Permite cambiar comportamiento sin editar código fuente.",
        project: "Research, refine y plan se manejan con configs YAML bajo `configs/`."
      },
      "Config": {
        term: "Config",
        plain: "Un archivo u objeto que le dice al software qué opciones usar.",
        business: "Las instrucciones operativas para esta corrida.",
        technical: "Parámetros estructurados parseados y validados antes de ejecutar.",
        matters: "Separa código reutilizable de decisiones específicas de una corrida.",
        project: "Las configs eligen topic, dimensiones, estrategia, backends, herramientas, scoring y estilo."
      },
      "Artifact": {
        term: "Artefacto",
        plain: "Un archivo producido por un proceso.",
        business: "Un entregable o registro que queda después del trabajo.",
        technical: "Salida durable como markdown, JSON, HTML, logs, traces o reportes.",
        matters: "Los artefactos hacen el trabajo inspeccionable y reutilizable después de la llamada al modelo.",
        project: "Las corridas producen `results.tsv`, `knowledge_base.md`, `synthesis.md`, `report.html` y logs."
      },
      "HTML": {
        term: "HTML",
        plain: "El formato estándar usado para estructurar páginas web.",
        business: "La estructura del documento que la gente abre en un navegador.",
        technical: "Etiquetas que describen headings, secciones, links, scripts y layout hooks.",
        matters: "HTML permite convertir trabajo generado en una página legible o interactiva.",
        project: "La presentación, dashboard y glosario son HTML estático en `docs/showcase/`."
      },
      "CSS": {
        term: "CSS",
        plain: "Las reglas que controlan cómo se ve una página web.",
        business: "La guía visual y de layout aplicada a un documento.",
        technical: "Selectores y declaraciones que controlan color, espaciado, tipografía, grids y responsive.",
        matters: "Hace que el mismo contenido sea legible, pulido y consistente.",
        project: "El glosario reutiliza el estilo CRT/phosphor del deck."
      },
      "JavaScript": {
        term: "JavaScript",
        plain: "El lenguaje que los navegadores usan para hacer páginas interactivas.",
        business: "La capa de comportamiento que permite responder a clics y escritura.",
        technical: "Código cliente que manipula la página y maneja eventos.",
        matters: "Permite búsqueda, filtros, atajos y controles sin backend.",
        project: "La búsqueda del glosario corre en JavaScript del navegador sobre datos estáticos."
      },
      "Static Site": {
        term: "Sitio estático",
        plain: "Una página web que funciona desde archivos sin una aplicación de servidor.",
        business: "Un folleto autocontenido con pestañas interactivas.",
        technical: "HTML, CSS, JavaScript y archivos de datos servidos tal cual.",
        matters: "Las páginas estáticas son fáciles de compartir, hospedar y abrir localmente.",
        project: "El glosario es estático: todos los conceptos están precargados en `glossary-data.js`."
      },
      "Claude Code": {
        term: "Claude Code",
        plain: "La experiencia/herramienta de Anthropic para usar Claude en un entorno de desarrollo.",
        business: "Un asistente de IA por suscripción que ayuda a inspeccionar y modificar proyectos de software.",
        technical: "Una interfaz de agente por CLI que puede envolverse como backend local.",
        matters: "Puede dar razonamiento fuerte, pero su CLI depende de auth, versión y límites de uso.",
        project: "La corrida AWS usó Claude CLI como backend principal de research y síntesis."
      },
      "Claude": {
        term: "Claude",
        plain: "Una familia de modelos de IA creada por Anthropic.",
        business: "Un experto de IA de un proveedor, disponible en niveles de capacidad/costo.",
        technical: "Una familia de modelos accesible por productos, CLI y APIs.",
        matters: "Distintas familias de modelos tienen fortalezas y puntos ciegos distintos.",
        project: "Las configs pueden usar variantes de Claude como primary, research, synthesis o utility."
      },
      "Codex": {
        term: "Codex",
        plain: "Herramienta/modelo de OpenAI orientado a tareas de software y razonamiento.",
        business: "Otro especialista de IA, útil como revisor independiente por venir de otra familia.",
        technical: "Backend CLI o API que ejecuta prompts e interactúa con flujos de desarrollo.",
        matters: "Usar Codex como crítico o juez crea revisión cross-family en vez de autoevaluación.",
        project: "La config adversarial AWS usa Codex como crítico y juez."
      },
      "Gemini": {
        term: "Gemini",
        plain: "La familia de modelos de IA de Google.",
        business: "Otra opción de proveedor de IA que puede compararse o intercambiarse.",
        technical: "Familia de modelos accesible por productos Google, APIs e integraciones CLI.",
        matters: "Varios proveedores hacen que el harness dependa menos de una sola familia.",
        project: "El registro de backends incluye adaptadores Gemini CLI y API."
      },
      "GitHub Copilot": {
        term: "GitHub Copilot",
        plain: "El asistente de IA de GitHub para desarrollo de software.",
        business: "Un asistente de coding integrado con la plataforma que muchos desarrolladores ya usan.",
        technical: "Un asistente de código accesible desde editor y flujos CLI.",
        matters: "Sirve como perspectiva separada en investigaciones o implementación centradas en desarrollo.",
        project: "La corrida LocalStack del showcase usó Copilot como backend de research."
      },
      "Model Family": {
        term: "Familia de modelo",
        plain: "Un grupo de modelos relacionados por organización o linaje de entrenamiento.",
        business: "Distintas consultoras con hábitos, fortalezas y puntos ciegos distintos.",
        technical: "Modelos que comparten proveedor, arquitectura, datos o comportamiento de alineación.",
        matters: "La crítica entre familias vale más que pedirle al mismo modelo que se evalúe.",
        project: "La presentación enfatiza Claude, Codex, Copilot y Gemini como familias reemplazables."
      },
      "Backend": {
        term: "Backend",
        plain: "El servicio o herramienta concreta que el harness llama para hacer trabajo.",
        business: "El proveedor o trabajador asignado a un rol.",
        technical: "Un adaptador que implementa un contrato común de invocación.",
        matters: "El mismo harness puede correr con distintos backends si el contrato es estable.",
        project: "Los backends se configuran por IDs de proveedor y se asignan a roles."
      },
      "Frontend": {
        term: "Frontend",
        plain: "La parte del software que las personas ven e interactúan.",
        business: "La pantalla, mostrador o dashboard por donde trabaja el usuario.",
        technical: "HTML, CSS, JavaScript y comportamiento del navegador.",
        matters: "Un buen frontend hace entendibles sistemas complejos.",
        project: "El deck, dashboard, presenter view y glosario son artefactos frontend."
      },
      "Backend Service": {
        term: "Servicio backend",
        plain: "La parte del software que corre detrás de escena y maneja lógica, almacenamiento o integraciones.",
        business: "La oficina de back office que procesa solicitudes después de que el usuario las envía.",
        technical: "Código server-side, workers, colas, bases de datos o APIs.",
        matters: "Algunas apps necesitan backend para datos vivos, autenticación o trabajo largo.",
        project: "El glosario no necesita backend porque todos los datos son estáticos y precargados."
      },
      "Repository": {
        term: "Repositorio",
        plain: "Una carpeta con código, historial, docs, configs y tests de un proyecto de software.",
        business: "La carpeta compartida del proyecto para el equipo de software.",
        technical: "Normalmente un working tree controlado por Git con código y artefactos.",
        matters: "Los agentes necesitan contexto del repo para hacer cambios con seguridad.",
        project: "Este showcase vive dentro del repositorio bajo `docs/showcase/`."
      },
      "Git": {
        term: "Git",
        plain: "Un sistema para rastrear cambios en archivos a lo largo del tiempo.",
        business: "Historial de versiones de documentos con ramas y revisión de cambios.",
        technical: "Control de versiones distribuido con commits, diffs, branches y merges.",
        matters: "Permite revisar cambios, recuperar versiones previas y colaborar.",
        project: "Los agentes deben respetar cambios existentes y no revertir ediciones del usuario."
      },
      "Diff": {
        term: "Diff",
        plain: "Una vista de qué cambió entre dos versiones de archivos.",
        business: "Una vista de edición con líneas agregadas y quitadas.",
        technical: "Comparación por líneas usada en code review y patches.",
        matters: "Los diffs hacen inspeccionables los cambios antes de aceptarlos.",
        project: "Las ediciones se hacen como patches para mantener los cambios revisables."
      },
      "Code Review": {
        term: "Revisión de código",
        plain: "Una revisión estructurada de cambios de software antes de aceptarlos.",
        business: "Peer review aplicado al trabajo de software.",
        technical: "Revisores inspeccionan diffs por bugs, regresiones, diseño y falta de tests.",
        matters: "Detecta problemas que el autor original no vio.",
        project: "La analogía de crítica adversarial se parece a code review: ojos distintos detectan fallos distintos."
      },
      "Heuristic": {
        term: "Heurística",
        plain: "Una regla práctica que da una estimación útil sin demostrar la respuesta perfecta.",
        business: "Un filtro o checklist: no es la verdad final, pero da una señal rápida y detecta problemas obvios.",
        technical: "Una regla determinística de scoring o decisión basada en señales medibles.",
        matters: "Las heurísticas hacen parte de la evaluación predecible y barata, sin delegar todo a otro modelo.",
        project: "El scoring de research usa señales heurísticas como foco, citas, datos concretos, estructura y longitud."
      },
      "Deterministic": {
        term: "Determinístico",
        plain: "Un proceso que da el mismo resultado cada vez cuando la entrada y las reglas son iguales.",
        business: "Una calculadora: escribes los mismos números y obtienes la misma respuesta.",
        technical: "No hay aleatoriedad ni cambios de variables ocultas que afecten el resultado.",
        matters: "Las partes determinísticas hacen los sistemas más fáciles de testear, depurar, auditar y confiar.",
        project: "Parseo de config, rollback de archivos, validación JSON y scoring heurístico buscan ser determinísticos."
      },
      "Non-Deterministic": {
        term: "No determinístico",
        plain: "Un proceso que puede producir resultados válidos diferentes incluso con entradas similares.",
        business: "Preguntar a tres expertos lo mismo y recibir énfasis distintos.",
        technical: "Sampling, comportamiento del modelo, timing, herramientas externas o datos cambiantes pueden alterar la salida.",
        matters: "Los sistemas con LLM necesitan verificación, logs y retries porque las respuestas no siempre son repetibles.",
        project: "El loop adversarial trata la salida del modelo como incierta y la controla con scoring, crítica y auditoría."
      },
      "Temperature": {
        term: "Temperatura",
        plain: "Un ajuste que afecta qué tan variada o conservadora es la salida de un modelo.",
        business: "Un dial de creatividad: bajo para texto legal predecible, alto para brainstorming.",
        technical: "Un parámetro de sampling que cambia la distribución de probabilidad al elegir próximos tokens.",
        matters: "Más variación puede ayudar a explorar, pero puede reducir repetibilidad.",
        project: "El framework favorece scoring explícito y revisión repetida porque las salidas pueden variar incluso con buenos prompts."
      },
      "Hallucination": {
        term: "Alucinación",
        plain: "Cuando un modelo produce información que suena segura pero es falsa o no está sustentada.",
        business: "Un consultor inventando una fuente o detalle en vez de admitir incertidumbre.",
        technical: "Texto generado que no está anclado en contexto confiable, evidencia o resultados de herramientas.",
        matters: "Las alucinaciones son una razón central para exigir citas, verificación y revisión adversarial.",
        project: "Crítica, evidencia, trust classes y cobertura de citas son defensas contra investigación alucinada."
      },
      "Grounding": {
        term: "Grounding",
        plain: "Conectar una respuesta con evidencia, datos o material fuente específico.",
        business: "Una recomendación con recibos adjuntos.",
        technical: "Restringir o validar salida generada contra contexto recuperado, citas, herramientas o artefactos.",
        matters: "Hace que la salida del modelo sea más defendible y menos dependiente de memoria interna.",
        project: "El loop de research ancla reportes finales en hallazgos aceptados, citas y artefactos de evidencia."
      },
      "Inference": {
        term: "Inferencia",
        plain: "El momento en que se usa un modelo ya entrenado para producir una respuesta.",
        business: "Pedirle una respuesta al experto después de que ya fue entrenado.",
        technical: "Ejecutar un forward pass sobre tokens de entrada para generar tokens de salida.",
        matters: "La mayoría del uso cotidiano de IA es inferencia, no entrenamiento.",
        project: "Cada llamada a backend en el loop de investigación es una llamada de inferencia envuelta por el harness."
      },
      "Training": {
        term: "Entrenamiento",
        plain: "El proceso costoso de enseñar un modelo con grandes cantidades de datos antes de usarlo.",
        business: "Educar al experto antes de que entre a la empresa.",
        technical: "Optimizar pesos del modelo sobre datasets usando cómputo.",
        matters: "La mayoría de equipos no entrena modelos fundacionales; construye harnesses alrededor de modelos entrenados.",
        project: "Este framework no entrena modelos. Orquesta backends de modelos existentes."
      },
      "Fine-Tuning": {
        term: "Fine-tuning",
        plain: "Entrenamiento adicional que adapta un modelo a una tarea o estilo más estrecho.",
        business: "Tomar un experto general y entrenarlo en el playbook de tu empresa.",
        technical: "Actualizar pesos del modelo o pesos adaptadores con ejemplos específicos.",
        matters: "Puede ayudar en tareas repetidas especializadas, pero no es la primera solución para problemas de orquestación.",
        project: "El proyecto se enfoca en harness engineering; cambia comportamiento con configs, prompts, roles y scoring."
      },
      "Zero-Shot": {
        term: "Zero-shot",
        plain: "Pedirle al modelo hacer una tarea sin darle ejemplos del resultado deseado.",
        business: "Dar instrucciones pero ningún ejemplo de entregable.",
        technical: "Ejecución de tarea solo desde instrucciones, sin ejemplos en contexto.",
        matters: "Es rápido, pero ejemplos o contratos suelen mejorar consistencia.",
        project: "Algunas llamadas utility pueden ser zero-shot; etapas importantes usan más contexto y contratos."
      },
      "Few-Shot": {
        term: "Few-shot",
        plain: "Darle al modelo algunos ejemplos para que imite el patrón deseado.",
        business: "Mostrar dos buenos memos antes de pedir un tercero.",
        technical: "Aprendizaje en contexto mediante ejemplos incluidos en el prompt.",
        matters: "Los ejemplos pueden mejorar formato, tono y consistencia sin entrenar otro modelo.",
        project: "Los templates de prompt y contratos de salida pueden incluir ejemplos cuando importa la estructura."
      },
      "Chain-of-Thought": {
        term: "Chain-of-thought",
        plain: "Los pasos intermedios de razonamiento del modelo mientras llega a una respuesta.",
        business: "La hoja de trabajo detrás de la recomendación final.",
        technical: "Tokens de razonamiento privados o expuestos usados para planear, derivar o revisar una respuesta.",
        matters: "El razonamiento detallado puede ayudar en tareas complejas, pero se deben verificar salidas y no confiar solo en el texto de razonamiento.",
        project: "El framework registra decisiones, scores, críticas y evidencia en vez de depender solo de razonamiento oculto."
      },
      "Structured Output": {
        term: "Salida estructurada",
        plain: "Salida del modelo restringida a un formato predecible que el software puede leer.",
        business: "Un formulario lleno en vez de un ensayo libre.",
        technical: "Salida que sigue un schema como campos JSON, enums, arrays o reglas de validación.",
        matters: "Permite que el harness valide, puntúe, enrute y guarde resultados con confiabilidad.",
        project: "Resultados de juez, gaps, rúbricas y registros de auditoría usan datos estructurados cuando es posible."
      },
      "Schema": {
        term: "Schema",
        plain: "Una definición de qué campos y formas deben tener los datos.",
        business: "Una plantilla de formulario que dice qué campos son obligatorios y qué valores se permiten.",
        technical: "Un contrato estructural para validar objetos, arrays, tipos y enums.",
        matters: "Evita que datos vagos o mal formados entren silenciosamente al sistema.",
        project: "Modelos de config, salidas de juez, gap entries y artefactos usan validación tipo schema."
      },
      "Latency": {
        term: "Latencia",
        plain: "Cuánto tarda en llegar una respuesta después de hacer una solicitud.",
        business: "El tiempo de espera entre hacer una pregunta y recibir la respuesta.",
        technical: "Tiempo transcurrido para una llamada, request, comando o paso de workflow.",
        matters: "Corridas largas pueden ser útiles, pero necesitan logs de progreso, retries y buenas reglas de parada.",
        project: "Las iteraciones de research pueden tardar minutos por llamadas a modelos, herramientas, crítica y scoring."
      },
      "Timeout": {
        term: "Timeout",
        plain: "El tiempo máximo permitido para una operación antes de tratarla como fallida.",
        business: "Si un proveedor no responde antes del plazo, el proceso pasa a recuperación.",
        technical: "Un límite de runtime para subprocesses, APIs, herramientas o iteraciones.",
        matters: "Evita que llamadas trabadas bloqueen todo el workflow indefinidamente.",
        project: "Las configs de research definen `timeout_seconds` por llamada a backend."
      },
      "Variance": {
        term: "Varianza",
        plain: "Cuánto puede cambiar la respuesta al mismo prompt entre corridas del mismo modelo o entre modelos distintos.",
        business: "Dos analistas que responden la misma pregunta pueden dar respuestas distintas — esa dispersión es varianza. Sirve como señal cuando la podés medir; es peligrosa cuando no.",
        technical: "Dispersión estadística de las salidas del modelo dado el mismo input. Viene de la temperatura de sampling, el decoding estocástico y los sesgos de entrenamiento específicos de cada familia.",
        matters: "Alta varianza más una sola muestra = no determinístico y no auditable. No podés confiar en una respuesta si no sabés cuánto habría cambiado en otra corrida.",
        project: "El framework convierte la varianza en triangulación productiva: ensemble corre dos backends en paralelo, parallel los compite a todos, adversarial mete un crítico de otra familia. Cada patrón usa la varianza inter-modelo como señal en vez de esconderla detrás de una sola muestra."
      }
    }
  }
};
