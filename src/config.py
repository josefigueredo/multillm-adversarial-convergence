"""Research configuration loading and validation.

Provides frozen dataclasses for scoring, execution, and top-level research
configuration.  Configs are loaded from YAML files via
``ResearchConfig.from_yaml``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("autoresearch")

from .backends import VALID_BACKENDS

# Valid multi-backend strategy names.
VALID_STRATEGIES = ("single", "ensemble", "adversarial", "parallel", "serial", "specialist")


@dataclass(frozen=True)
class BackendsConfig:
    """Role-to-backend mapping for multi-backend strategies.

    Attributes:
        primary: Backend for hypothesis generation and synthesis.
        research: Backends used for the execution phase.  In ensemble/parallel
            strategies multiple backends research independently.
        judge: Backend used for scoring/evaluation (should differ from
            research backends to avoid confirmation bias).
        utility: Backend used for mechanical tasks (compression).
    """

    primary: str = "claude"
    research: tuple[str, ...] = ("claude",)
    judge: str = ""  # empty → falls back to primary
    utility: str = ""  # empty → falls back to primary

    @property
    def judge_or_primary(self) -> str:
        return self.judge or self.primary

    @property
    def utility_or_primary(self) -> str:
        return self.utility or self.primary

    def all_backend_names(self) -> set[str]:
        """Return the set of all backend names referenced in this config."""
        names = {self.primary, *self.research}
        if self.judge:
            names.add(self.judge)
        if self.utility:
            names.add(self.utility)
        return names


@dataclass(frozen=True)
class StrategyConfig:
    """Strategy-specific settings for multi-backend research.

    Attributes:
        merge_mode: How to combine results from parallel execution.
            ``"best"`` keeps only the highest-scoring result.
            ``"union"`` merges all results that pass the threshold.
        merge_threshold: Minimum score for a result to be merge-eligible
            (only used when ``merge_mode="union"``).
        critique_depth: Depth of adversarial critique.
            ``"light"`` does a factual spot-check, ``"standard"`` is balanced,
            ``"thorough"`` is line-by-line.
        refiner_sees_draft: Whether the refiner backend receives the
            drafter's output as context (serial strategy).
        max_parallel: Maximum number of backends to run concurrently.
        stagger_seconds: Delay between launching parallel backends to
            reduce simultaneous rate-limit pressure.
    """

    merge_mode: str = "best"
    merge_threshold: float = 40.0
    critique_depth: str = "standard"
    refiner_sees_draft: bool = True
    max_parallel: int = 3
    stagger_seconds: int = 5


@dataclass(frozen=True)
class MethodologyConfig:
    """Optional methodology guidance for more rigorous research runs.

    Attributes:
        question: Explicit research question framing.
        scope: Boundaries or intended audience/scope of the investigation.
        inclusion_criteria: Evidence or source types that should be preferred.
        exclusion_criteria: Evidence or source types that should be avoided.
        preferred_source_types: Ordered preferred source categories.
        recency_days: Preferred freshness window for unstable information.
    """

    question: str = ""
    scope: str = ""
    inclusion_criteria: tuple[str, ...] = ()
    exclusion_criteria: tuple[str, ...] = ()
    preferred_source_types: tuple[str, ...] = ()
    recency_days: int = 0


@dataclass(frozen=True)
class ScoringConfig:
    """Controls how each research iteration is scored.

    Attributes:
        min_dimensions_per_iteration: Minimum dimensions expected per iteration
            for full heuristic credit.
        target_dimensions_total: Target number of dimensions across all
            iterations.
        evidence_types: Tuple of evidence type labels the heuristic scorer
            looks for (e.g. ``"comparison_table"``, ``"pricing_data"``).
    """

    min_dimensions_per_iteration: int = 1
    target_dimensions_total: int = 10
    evidence_types: tuple[str, ...] = (
        "comparison_table",
        "pricing_data",
        "code_example",
        "architecture_diagram_description",
        "trade_off_analysis",
    )


@dataclass(frozen=True)
class EvaluationConfig:
    """Optional evaluation settings for benchmark/baseline comparisons.

    Attributes:
        benchmark_id: Optional benchmark/task identifier for the run.
        run_baselines: Whether to generate a single-pass baseline answer and compare it.
        expected_dimensions: Optional benchmark expectations for covered dimensions.
        required_keywords: Optional benchmark keywords expected in the synthesis.
        reference_runs: Optional prior output directories for consistency / strategy comparison.
        semantic_calibration: Whether to derive a calibrated semantic quality score.
        semantic_review: Whether to run an optional final semantic judge pass over synthesis.
    """

    benchmark_id: str = ""
    run_baselines: bool = False
    expected_dimensions: tuple[str, ...] = ()
    required_keywords: tuple[str, ...] = ()
    reference_runs: tuple[str, ...] = ()
    semantic_calibration: bool = True
    semantic_review: bool = False


@dataclass(frozen=True)
class ReportingConfig:
    """Optional report rendering settings.

    Attributes:
        export_html: Whether to emit a human-readable HTML report artifact.
        export_pdf: Whether to emit a human-readable PDF report artifact.
        report_title: Optional override for the HTML report title.
    """

    export_html: bool = True
    export_pdf: bool = False
    report_title: str = ""


@dataclass(frozen=True)
class ExecutionConfig:
    """Runtime parameters for the research loop.

    Attributes:
        max_iterations: Maximum iterations before stopping.  ``0`` means
            infinite (run until interrupted).
        compress_every: Compress the knowledge base every *N* iterations.
        allowed_tools: Comma-separated list of tools available to the agent.
        max_turns: Maximum agent turns per CLI invocation.
        timeout_seconds: Per-invocation timeout in seconds.
        backend: CLI backend to use (``"claude"``, ``"codex"``, ``"gemini"``,
            or ``"copilot"``).
        model: Model name (backend-specific, e.g. ``"sonnet"`` for Claude).
        max_budget_per_call: USD cap per CLI invocation (backends that don't
            support per-call budgets ignore this).
        lightweight_mode: Prefer shorter prompts/artifacts and stricter goal-shape
            obedience for trivial or smoke-test runs.
        isolate_backend_context: Prefer running backend CLIs from an isolated
            temp working directory instead of the repo root. The orchestrator
            only applies this automatically to compatible backends; users can
            still force it per backend in future extensions.
        sanitize_backend_env: Prefer passing a reduced subprocess environment
            to backend CLIs. Like isolated context, this is applied only when
            the backend is marked compatible.
    """

    max_iterations: int = 0
    compress_every: int = 5
    allowed_tools: str = "WebSearch,WebFetch,Read,Bash,Glob,Grep"
    max_turns: int = 10
    timeout_seconds: int = 600
    backend: str = "claude"
    model: str = "sonnet"
    max_budget_per_call: float = 0.50
    lightweight_mode: bool = False
    isolate_backend_context: bool = True
    sanitize_backend_env: bool = True
    strategy: str = "single"
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)


@dataclass(frozen=True)
class ResearchConfig:
    """Top-level research configuration loaded from a YAML file.

    Attributes:
        topic: The research question.
        goal: Description of the desired deliverable.
        dimensions: Tuple of dimensions to explore.
        scoring: Scoring parameters.
        execution: Execution / runtime parameters.
    """

    topic: str
    goal: str
    dimensions: tuple[str, ...]
    methodology: MethodologyConfig = field(default_factory=MethodologyConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> ResearchConfig:
        """Load a research config from a YAML file.

        The YAML must contain a top-level ``research`` key with at least a
        ``topic`` field.  All other fields are optional and fall back to
        dataclass defaults.

        Args:
            path: Path to the YAML config file.

        Returns:
            A validated ``ResearchConfig`` instance.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is empty, malformed, or missing required
                fields.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")

        if "research" not in raw:
            raise ValueError("Config file must contain a top-level 'research' key")

        research: dict[str, Any] = raw["research"]

        if "topic" not in research:
            raise ValueError("Config 'research' section must contain a 'topic' field")

        # --- Methodology ------------------------------------------------------
        methodology_raw: dict[str, Any] = research.get("methodology", {})
        methodology = MethodologyConfig(
            question=methodology_raw.get("question", ""),
            scope=methodology_raw.get("scope", ""),
            inclusion_criteria=tuple(methodology_raw.get("inclusion_criteria", [])),
            exclusion_criteria=tuple(methodology_raw.get("exclusion_criteria", [])),
            preferred_source_types=tuple(methodology_raw.get("preferred_source_types", [])),
            recency_days=methodology_raw.get("recency_days", 0),
        )

        # --- Evaluation -------------------------------------------------------
        evaluation_raw: dict[str, Any] = research.get("evaluation", {})
        evaluation = EvaluationConfig(
            benchmark_id=evaluation_raw.get("benchmark_id", ""),
            run_baselines=evaluation_raw.get("run_baselines", False),
            expected_dimensions=tuple(evaluation_raw.get("expected_dimensions", [])),
            required_keywords=tuple(evaluation_raw.get("required_keywords", [])),
            reference_runs=tuple(evaluation_raw.get("reference_runs", [])),
            semantic_calibration=evaluation_raw.get("semantic_calibration", True),
            semantic_review=evaluation_raw.get("semantic_review", False),
        )

        # --- Reporting --------------------------------------------------------
        reporting_raw: dict[str, Any] = research.get("reporting", {})
        reporting = ReportingConfig(
            export_html=reporting_raw.get("export_html", True),
            export_pdf=reporting_raw.get("export_pdf", False),
            report_title=reporting_raw.get("report_title", ""),
        )

        # --- Scoring ----------------------------------------------------------
        scoring_raw: dict[str, Any] = research.get("scoring", {})
        evidence = scoring_raw.get("evidence_types")
        scoring_defaults = ScoringConfig()
        scoring = ScoringConfig(
            min_dimensions_per_iteration=scoring_raw.get(
                "min_dimensions_per_iteration",
                scoring_defaults.min_dimensions_per_iteration,
            ),
            target_dimensions_total=scoring_raw.get(
                "target_dimensions_total",
                scoring_defaults.target_dimensions_total,
            ),
            evidence_types=tuple(evidence) if evidence else scoring_defaults.evidence_types,
        )

        # --- Execution --------------------------------------------------------
        exec_raw: dict[str, Any] = research.get("execution", {})
        exec_defaults = ExecutionConfig()

        backend = exec_raw.get("backend", exec_defaults.backend)
        if backend not in VALID_BACKENDS:
            raise ValueError(
                f"Invalid backend '{backend}'. Must be one of: {', '.join(VALID_BACKENDS)}"
            )

        model = exec_raw.get("model", exec_defaults.model)

        max_budget = exec_raw.get("max_budget_per_call", exec_defaults.max_budget_per_call)
        if max_budget < 0:
            raise ValueError(f"max_budget_per_call must be non-negative, got {max_budget}")

        timeout = exec_raw.get("timeout_seconds", exec_defaults.timeout_seconds)
        if timeout <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout}")

        # --- Strategy / multi-backend -----------------------------------------
        strategy = exec_raw.get("strategy", "single")
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(VALID_STRATEGIES)}"
            )

        backends_raw: dict[str, Any] = exec_raw.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get("research", [backend])
            if isinstance(research_val, str):
                research_val = [research_val]
            for name in research_val:
                if name not in VALID_BACKENDS:
                    raise ValueError(f"Invalid research backend '{name}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            primary = backends_raw.get("primary", backend)
            if primary not in VALID_BACKENDS:
                raise ValueError(f"Invalid primary backend '{primary}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            judge = backends_raw.get("judge", "")
            if judge and judge not in VALID_BACKENDS:
                raise ValueError(f"Invalid judge backend '{judge}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            utility = backends_raw.get("utility", "")
            if utility and utility not in VALID_BACKENDS:
                raise ValueError(f"Invalid utility backend '{utility}'. Must be one of: {', '.join(VALID_BACKENDS)}")
            backends_config = BackendsConfig(
                primary=primary,
                research=tuple(research_val),
                judge=judge,
                utility=utility,
            )
            # Warn if judge is also a researcher (defeats blind review)
            if strategy != "single" and judge and judge in research_val:
                log.warning(
                    "Judge backend '%s' is also a research backend — blind review is compromised.",
                    judge,
                )
        else:
            # Backward compat: single backend → populate roles from it
            backends_config = BackendsConfig(
                primary=backend,
                research=(backend,),
            )

        strat_raw: dict[str, Any] = exec_raw.get("strategy_config", {})
        strategy_config = StrategyConfig(
            merge_mode=strat_raw.get("merge_mode", "best"),
            merge_threshold=strat_raw.get("merge_threshold", 40.0),
            critique_depth=strat_raw.get("critique_depth", "standard"),
            refiner_sees_draft=strat_raw.get("refiner_sees_draft", True),
            max_parallel=strat_raw.get("max_parallel", 3),
            stagger_seconds=strat_raw.get("stagger_seconds", 5),
        )

        execution = ExecutionConfig(
            max_iterations=exec_raw.get("max_iterations", exec_defaults.max_iterations),
            compress_every=exec_raw.get("compress_every", exec_defaults.compress_every),
            allowed_tools=exec_raw.get("allowed_tools", exec_defaults.allowed_tools),
            max_turns=exec_raw.get("max_turns", exec_defaults.max_turns),
            timeout_seconds=timeout,
            backend=backend,
            model=model,
            max_budget_per_call=max_budget,
            lightweight_mode=exec_raw.get("lightweight_mode", exec_defaults.lightweight_mode),
            isolate_backend_context=exec_raw.get(
                "isolate_backend_context",
                exec_defaults.isolate_backend_context,
            ),
            sanitize_backend_env=exec_raw.get(
                "sanitize_backend_env",
                exec_defaults.sanitize_backend_env,
            ),
            strategy=strategy,
            backends=backends_config,
            strategy_config=strategy_config,
        )

        return cls(
            topic=research["topic"],
            goal=research.get("goal", research["topic"]),
            dimensions=tuple(research.get("dimensions", [])),
            methodology=methodology,
            evaluation=evaluation,
            reporting=reporting,
            scoring=scoring,
            execution=execution,
        )


# ---------------------------------------------------------------------------
# Document-mode configuration (loaded by `refine` subcommand)
# ---------------------------------------------------------------------------

VALID_PERSONA_MODES = ("parallel", "serial")


@dataclass(frozen=True)
class PersonaConfig:
    """A single reviewer persona for the document convergence loop."""

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class ArtifactConfig:
    """A secondary artifact generated in Phase 2 (Expansion)."""

    name: str
    layer: str
    prompt_file: str = ""
    review: bool = True


@dataclass(frozen=True)
class SourceFileConfig:
    """A single source file injected into agent prompts during document convergence.

    Each instance represents one resolved file (glob patterns are already expanded
    by ``_parse_source_files`` before construction).

    Attributes:
        path: Absolute path to the file on disk.  Always a single concrete file —
            never a glob pattern or directory.
        roles: Agent roles that receive this file's content.  Valid values are
            ``"builder"``, ``"challenger"``, any persona name declared in the config,
            or the sentinel ``"all"`` (expanded to all concrete roles at load time).
    """

    path: str
    roles: tuple[str, ...]


def _parse_source_files(
    raw_entries: list[dict[str, Any]],
    config_dir: Path,
    persona_names: set[str],
) -> tuple[SourceFileConfig, ...]:
    """Resolve ``source_files`` YAML entries into one ``SourceFileConfig`` per matched file.

    Path resolution rules (in priority order):

    1. **Glob** (pattern contains ``*``, ``?``, or ``[``):
       - Absolute glob (starts with ``/``): expanded via ``Path('/').glob(relative_pattern)``
         so that ``**`` traversal works correctly.
       - Relative glob: expanded relative to ``config_dir``.
       - A glob that matches nothing logs a warning and is silently skipped.

    2. **Absolute literal** (starts with ``/``, no glob chars):
       Validated with ``Path.exists()``; raises ``ValueError`` if missing.

    3. **Relative literal**:
       Resolved as ``config_dir / pattern``; raises ``ValueError`` if missing.

    Role expansion:
       ``"all"`` expands to ``{"builder", "challenger"} | persona_names``.
       Unknown role names are stored as-is and silently accepted (they will simply
       never match an agent call, which is harmless).

    Args:
        raw_entries: Parsed YAML list of ``{path: ..., roles: [...]}`` dicts.
        config_dir: Directory containing the config file; used to resolve relative paths.
        persona_names: Concrete persona names declared in the config (used to expand ``"all"``).

    Returns:
        A tuple of ``SourceFileConfig`` instances, one per matched file.

    Raises:
        ValueError: If a literal (non-glob) path does not exist on disk.
    """
    all_roles = {"builder", "challenger"} | persona_names
    result: list[SourceFileConfig] = []

    for entry in raw_entries:
        pattern: str = entry["path"]
        raw_roles: list[str] = entry.get("roles", ["builder"])

        roles: set[str] = set()
        for r in raw_roles:
            if r == "all":
                roles |= all_roles
            else:
                roles.add(r)
        roles_tuple = tuple(sorted(roles))

        is_absolute = Path(pattern).is_absolute()
        has_glob = any(c in pattern for c in "*?[")

        if has_glob:
            if is_absolute:
                p = Path(pattern)
                matched = sorted(Path('/').glob(str(p.relative_to('/'))))
            else:
                matched = sorted(config_dir.glob(pattern))
            if not matched:
                log.warning("source_files glob '%s' matched no files — skipping", pattern)
            for m in matched:
                result.append(SourceFileConfig(path=str(m), roles=roles_tuple))
        elif is_absolute:
            p = Path(pattern)
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))
        else:
            p = config_dir / pattern
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))

    return tuple(result)


@dataclass(frozen=True)
class DocumentConfig:
    """Top-level configuration for a document refinement run.

    Loaded from a YAML file with a top-level ``document:`` key via
    :meth:`from_yaml`.  Independent of ``ResearchConfig``.

    Attributes:
        topic: Short label for the document being refined (e.g. ``"Iris Platform"``).
        goal: One-paragraph description of what the finished document should achieve
            and who will consume it.
        primary_artifact: Filename of the main document produced by Phase 1
            (convergence).  Defaults to ``"PRD.md"``.
        source_material: Path or raw text injected into the Builder prompt as seed
            content for cycle 0.  Kept for backward compatibility alongside
            ``source_files``.
        convergence_cycles: Number of consecutive clean cycles (no accepted critiques)
            required before Phase 1 stops.
        max_cycles: Hard cap on total convergence cycles.  ``0`` means no cap.
        persona_mode: ``"parallel"`` runs all persona reviewers concurrently;
            ``"serial"`` runs them in declaration order.
        personas: Review personas executed each cycle.  Defaults to
            ``architect``, ``scrum_master``, and ``product_owner``.
        artifacts: Phase 2 companion documents derived from the converged PRD.
        source_files: Companion files injected as structured context into agent
            prompts.  Each entry targets specific roles (``builder``, ``challenger``,
            persona names, or ``"all"``).  See :class:`SourceFileConfig`.
        backends: Role-to-backend mapping for the convergence loop.
        strategy_config: Strategy-level tuning (e.g. ``critique_depth``).
    """

    topic: str
    goal: str
    primary_artifact: str = "PRD.md"
    source_material: str = ""
    convergence_cycles: int = 1
    max_cycles: int = 0
    persona_mode: str = "parallel"
    personas: tuple[PersonaConfig, ...] = (
        PersonaConfig("architect"),
        PersonaConfig("scrum_master"),
        PersonaConfig("product_owner"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    source_files: tuple[SourceFileConfig, ...] = ()
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "DocumentConfig":
        """Load a document config from a YAML file with a top-level ``document:`` key.

        Expected YAML structure (all keys except ``topic`` are optional)::

            document:
              topic: "Feature name"
              goal: "What the PRD should achieve"
              primary_artifact: "PRD.md"
              source_material: ""          # path or raw text for Builder seed
              convergence_cycles: 2
              max_cycles: 10
              persona_mode: parallel        # parallel | serial
              personas:
                - name: architect
                - name: scrum_master
                - name: product_owner
              source_files:
                - path: docs/**/*.md       # glob, absolute, or relative
                  roles: [builder, architect]
                - path: /abs/path/file.md
                  roles: [all]
              artifacts:
                - name: ARCHITECTURE.md
                  layer: execution
                  review: true
              backends:
                primary: claude
                research: [claude, gemini]
                judge: claude
                utility: gemini

        Args:
            path: Path to the YAML config file.  Relative ``source_files`` paths
                are resolved relative to this file's parent directory.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is malformed, missing required fields, or a
                literal (non-glob) ``source_files`` path is not found on disk.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        if "document" not in raw:
            raise ValueError("Config must contain a top-level 'document' key")

        doc: dict[str, Any] = raw["document"]

        if "topic" not in doc:
            raise ValueError("'document' section must contain a 'topic' field")

        persona_mode = doc.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        raw_personas = doc.get("personas", [])
        personas = tuple(
            PersonaConfig(name=p["name"], prompt_file=p.get("prompt_file", ""))
            for p in raw_personas
        ) if raw_personas else (
            PersonaConfig("architect"),
            PersonaConfig("scrum_master"),
            PersonaConfig("product_owner"),
        )

        config_dir = path.parent
        persona_names = {p.name for p in personas}
        source_files = _parse_source_files(
            doc.get("source_files", []), config_dir, persona_names
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in doc.get("artifacts", [])
        )

        backends_raw: dict[str, Any] = doc.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get("research", [backends_raw.get("primary", "claude")])
            if isinstance(research_val, str):
                research_val = [research_val]
            backends_cfg = BackendsConfig(
                primary=backends_raw.get("primary", "claude"),
                research=tuple(research_val),
                judge=backends_raw.get("judge", ""),
                utility=backends_raw.get("utility", ""),
            )
        else:
            backends_cfg = BackendsConfig()

        strat_raw: dict[str, Any] = doc.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )

        return cls(
            topic=doc["topic"],
            goal=doc.get("goal", doc["topic"]),
            primary_artifact=doc.get("primary_artifact", "PRD.md"),
            source_material=doc.get("source_material", ""),
            convergence_cycles=doc.get("convergence_cycles", 1),
            max_cycles=doc.get("max_cycles", 0),
            persona_mode=persona_mode,
            personas=personas,
            artifacts=artifacts,
            source_files=source_files,
            backends=backends_cfg,
            strategy_config=strategy_cfg,
        )


# ---------------------------------------------------------------------------
# Plan-mode configuration (loaded by `plan` subcommand)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanPersonaConfig:
    """A single reviewer persona for the plan convergence loop.

    Attributes:
        name: Persona identifier — used for role-based source file filtering
            and as the default prompt file stem.
        prompt_file: Override prompt template filename.  Defaults to
            ``plan_persona_{name}.md`` when empty.
    """

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class PlanConfig:
    """Top-level configuration for a plan refinement run.

    Loaded from a YAML file with a top-level ``plan:`` key via :meth:`from_yaml`.
    Independent of ``ResearchConfig`` and ``DocumentConfig``.

    Attributes:
        topic: Short label for the plan being refined.
        goal: What the finished plan should enable — e.g. "unambiguous enough
            that a senior engineer can execute without clarifying questions."
        primary_artifact: Filename of the main document produced by Phase 1.
            Defaults to ``"PLAN.md"``.
        source_material: Path or raw text injected into the Builder prompt as
            seed content for cycle 0.
        convergence_cycles: Consecutive clean cycles required before stopping.
            Defaults to ``2`` (stricter than document mode's ``1``).
        max_cycles: Hard cap on total convergence cycles.  ``0`` means no cap.
        persona_mode: ``"parallel"`` runs all personas concurrently;
            ``"serial"`` runs them in declaration order.
        personas: Review personas executed each cycle.  Defaults to all seven
            plan-specific personas.
        artifacts: Phase 2 companion documents derived from the converged plan.
        source_files: Companion files injected as structured context into agent
            prompts, with per-file role targeting.  See :class:`SourceFileConfig`.
        backends: Role-to-backend mapping for the convergence loop.
        strategy_config: Strategy-level tuning (e.g. ``critique_depth``).
    """

    topic: str
    goal: str
    primary_artifact: str = "PLAN.md"
    source_material: str = ""
    convergence_cycles: int = 2
    max_cycles: int = 10
    persona_mode: str = "parallel"
    personas: tuple[PlanPersonaConfig, ...] = (
        PlanPersonaConfig("architect"),
        PlanPersonaConfig("tech_lead"),
        PlanPersonaConfig("qa_engineer"),
        PlanPersonaConfig("ai_engineer"),
        PlanPersonaConfig("data_engineer"),
        PlanPersonaConfig("security_engineer"),
        PlanPersonaConfig("devils_advocate"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    source_files: tuple[SourceFileConfig, ...] = ()
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "PlanConfig":
        """Load a plan config from a YAML file with a top-level ``plan:`` key.

        Expected YAML structure (all keys except ``topic`` are optional)::

            plan:
              topic: "Feature name"
              goal: "What the plan should enable"
              primary_artifact: "PLAN.md"
              source_material: ""
              convergence_cycles: 2
              max_cycles: 10
              persona_mode: parallel        # parallel | serial
              personas:
                - name: architect
                - name: tech_lead
              source_files:
                - path: docs/**/*.md
                  roles: [builder, architect]
              artifacts:
                - name: RISK_REGISTER.md
                  layer: companion
                  review: false
              backends:
                primary: claude
                research: [claude, gemini]
                judge: claude
                utility: gemini

        Args:
            path: Path to the YAML config file.  Relative ``source_files`` paths
                are resolved relative to this file's parent directory.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is malformed, missing required fields, or a
                literal (non-glob) ``source_files`` path is not found on disk.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        if "plan" not in raw:
            raise ValueError("Config must contain a top-level 'plan' key")

        plan_raw: dict[str, Any] = raw["plan"]

        if "topic" not in plan_raw:
            raise ValueError("'plan' section must contain a 'topic' field")

        persona_mode = plan_raw.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        raw_personas = plan_raw.get("personas", [])
        personas: tuple[PlanPersonaConfig, ...]
        if raw_personas:
            personas = tuple(
                PlanPersonaConfig(name=p["name"], prompt_file=p.get("prompt_file", ""))
                for p in raw_personas
            )
        else:
            personas = (
                PlanPersonaConfig("architect"),
                PlanPersonaConfig("tech_lead"),
                PlanPersonaConfig("qa_engineer"),
                PlanPersonaConfig("ai_engineer"),
                PlanPersonaConfig("data_engineer"),
                PlanPersonaConfig("security_engineer"),
                PlanPersonaConfig("devils_advocate"),
            )

        config_dir = path.parent
        persona_names = {p.name for p in personas}
        source_files = _parse_source_files(
            plan_raw.get("source_files", []), config_dir, persona_names
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in plan_raw.get("artifacts", [])
        )

        backends_raw: dict[str, Any] = plan_raw.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get("research", [backends_raw.get("primary", "claude")])
            if isinstance(research_val, str):
                research_val = [research_val]
            backends_cfg = BackendsConfig(
                primary=backends_raw.get("primary", "claude"),
                research=tuple(research_val),
                judge=backends_raw.get("judge", ""),
                utility=backends_raw.get("utility", ""),
            )
        else:
            backends_cfg = BackendsConfig()

        strat_raw: dict[str, Any] = plan_raw.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )

        exec_defaults = ExecutionConfig()
        exec_raw: dict[str, Any] = plan_raw.get("execution", {})
        execution_cfg = ExecutionConfig(
            allowed_tools=exec_raw.get("allowed_tools", exec_defaults.allowed_tools),
            max_turns=exec_raw.get("max_turns", exec_defaults.max_turns),
            timeout_seconds=exec_raw.get("timeout_seconds", exec_defaults.timeout_seconds),
        )

        return cls(
            topic=plan_raw["topic"],
            goal=plan_raw.get("goal", plan_raw["topic"]),
            primary_artifact=plan_raw.get("primary_artifact", "PLAN.md"),
            source_material=plan_raw.get("source_material", ""),
            convergence_cycles=plan_raw.get("convergence_cycles", 2),
            max_cycles=plan_raw.get("max_cycles", 10),
            persona_mode=persona_mode,
            personas=personas,
            artifacts=artifacts,
            source_files=source_files,
            backends=backends_cfg,
            strategy_config=strategy_cfg,
            execution=execution_cfg,
        )
