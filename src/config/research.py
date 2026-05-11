"""Research-mode configuration (loaded by the ``research`` subcommand).

Holds the dataclasses that are specific to the research workflow —
scoring, evaluation/judges, discovery, methodology, reporting — and
the big ``ResearchConfig.from_yaml`` parser that builds them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..backends import VALID_BACKENDS
from ..output_style import VALID_OUTPUT_STYLES
from .common import (
    VALID_STRATEGIES,
    BackendsConfig,
    ExecutionConfig,
    ProviderConfig,
    _build_strategy_config_from_raw,
    _parse_providers_config,
    _validate_provider_references,
)
from .hitl import HitlConfig, _parse_hitl_config
from .security import SecurityConfig, _parse_security_config

log = logging.getLogger("autoresearch")


@dataclass(frozen=True)
class MethodologyConfig:
    """Optional methodology guidance for more rigorous research runs.

    Attributes:
        question: Explicit research question framing.
        scope: Boundaries or intended audience/scope of the investigation.
        review_type: Optional methodology label such as ``"systematic_review"``.
        inclusion_criteria: Evidence or source types that should be preferred.
        exclusion_criteria: Evidence or source types that should be avoided.
        search_sources: Declared search-source groups or source systems.
        stopping_criteria: Explicit stopping rules for the run.
        stopping_rationale: Why the stopping criteria are appropriate.
        scoring_rationale: Why the scoring contract is appropriate.
        preferred_source_types: Ordered preferred source categories.
        recency_days: Preferred freshness window for unstable information.
    """

    question: str = ""
    scope: str = ""
    review_type: str = ""
    inclusion_criteria: tuple[str, ...] = ()
    exclusion_criteria: tuple[str, ...] = ()
    search_sources: tuple[str, ...] = ()
    stopping_criteria: tuple[str, ...] = ()
    stopping_rationale: str = ""
    scoring_rationale: str = ""
    preferred_source_types: tuple[str, ...] = ()
    recency_days: int = 0


@dataclass(frozen=True)
class ScoringWeights:
    """Composite-formula weights for iteration scoring.

    Defaults preserve the legacy ``0.4 coverage + 0.6 quality`` formula
    by setting ``novelty_weight = 0`` — operators opt into the
    novelty-blended formula by setting it positive.

    When ``novelty_weight > 0``, the formula becomes:

        quality_blend = (1 - judge_novelty_share) * quality
                        + judge_novelty_share * (judge_novelty * 10)
        total = coverage_weight * coverage
              + quality_weight * quality_blend
              + novelty_weight * heuristic_novelty

    The three top-level weights should sum to 1.0; values are not
    re-normalised so operators can audit any drift.

    Attributes:
        coverage_weight: Weight on heuristic coverage score (default 0.4
            to preserve legacy behavior).
        quality_weight: Weight on the LLM judge quality score (default
            0.6 to preserve legacy behavior).
        novelty_weight: Weight on heuristic novelty (text overlap with
            the knowledge base).  Default 0.0 = legacy formula.
            Suggested calibrated value: 0.25.
        judge_novelty_share: Sub-weight inside the quality term: when
            > 0, blends the judge's per-axis ``novelty`` (1-10, scaled
            to 0-100) into the quality slot.  Default 0.3.
    """

    coverage_weight: float = 0.4
    quality_weight: float = 0.6
    novelty_weight: float = 0.0
    judge_novelty_share: float = 0.3
    depth_bonus: float = 0.0


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
            Deprecated: kept for backward-compat parsing but no longer
            drives the universal-signal heuristic introduced by the
            scoring plan's universal-signal redesign.
        weights: Composite-formula weights.  Defaults preserve the
            legacy 0.4 coverage + 0.6 quality formula; setting
            ``weights.novelty_weight > 0`` enables the novelty-blended
            formula.
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
    weights: ScoringWeights = field(default_factory=ScoringWeights)


@dataclass(frozen=True)
class DiscoveryConfig:
    """Controls how judge-emitted gaps are filtered before they enter
    ``state.discovered_dimensions``.

    Attributes:
        language_filter: ``"en"`` to drop gaps that read as Spanish via
            stop-word heuristic; ``"none"`` to disable.  Default ``"en"``.
        dedupe_threshold: Levenshtein-style similarity ratio (0..1) above
            which two gap topics are considered duplicates.  Default
            ``0.85``.  Tighter (closer to 1.0) accepts near-duplicates as
            distinct; looser (closer to 0.0) merges aggressively.
        promotion_enabled: When True, only gaps that pass the Phase 3
            promotion check enter the hypothesis pool.  When False
            (default), every gap that survives intake is auto-promoted —
            matching pre-Phase-3 behavior.  Operators opt in once they
            have multi-iteration runs to drive the convergence signal.
        promotion_min_occurrences: Number of distinct iterations a gap
            must appear in to be promoted by repetition alone.  Default
            ``2``.
        promotion_high_confidence: Mean confidence threshold for
            single-occurrence promotion.  Default ``8`` (judge confident
            enough to act on one-shot).
    """

    language_filter: str = "en"
    dedupe_threshold: float = 0.85
    promotion_enabled: bool = False
    promotion_min_occurrences: int = 2
    promotion_high_confidence: int = 8


@dataclass(frozen=True)
class JudgeConfig:
    """One member of a multi-judge ensemble.

    Scoring plan Proposal #4: optional multi-judge consensus.  When
    ``evaluation.judges`` lists 2+ entries, the scorer calls each in
    sequence and averages their scores weighted by ``weight`` —
    reducing single-judge variance.  Per-judge breakdowns end up in
    ``IterationScore.per_judge`` for transparency.

    Attributes:
        adapter: Backend adapter id (e.g. ``"claude-cli"``,
            ``"gemini-cli"``).  Resolved through the same backend
            registry used by the strategy's research backends.
        model: Model id passed to the adapter.  Optional; falls back
            to the adapter's default.
        weight: Relative weight of this judge in the consensus
            average.  Weights need not sum to 1; they're normalised at
            consensus time.  Default ``1.0``.
    """

    adapter: str
    model: str = ""
    weight: float = 1.0


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
    judges: tuple[JudgeConfig, ...] = ()
    judge_disagreement_threshold: int = 2


@dataclass(frozen=True)
class OutputStyleOverrides:
    """Optional run-synthesis style overrides layered on top of output_style."""

    include_executive_summary: bool | None = None
    include_comparison_table: bool | None = None
    include_methodology: bool | None = None
    include_limitations: bool | None = None
    include_next_actions: bool | None = None
    section_order: str = ""  # "" | standard | recommendation_first | evidence_first
    recommendation_mode: str = ""  # "" | ranked | decision_only
    citation_mode: str = ""  # "" | inline_links | references_section


@dataclass(frozen=True)
class ReportingConfig:
    """Optional report rendering settings.

    Attributes:
        export_html: Whether to emit a human-readable HTML report artifact.
        export_pdf: Whether to emit a human-readable PDF report artifact.
        report_title: Optional override for the HTML report title.
        output_style: Run-mode synthesis prose/structure profile.
        style_overrides: Optional run-mode synthesis override knobs layered on
            top of the selected output style.
        capture_raw_backend_outputs: Whether future raw backend output capture
            is enabled. Default-off by policy.
        raw_backend_output_max_chars: Size cap for any future captured raw
            backend payloads.
        raw_backend_output_redact: Whether future raw payload capture should
            redact sensitive fields before persistence.
    """

    export_html: bool = True
    export_pdf: bool = False
    report_title: str = ""
    output_style: str = "default"
    style_overrides: OutputStyleOverrides = field(default_factory=OutputStyleOverrides)
    capture_raw_backend_outputs: bool = False
    raw_backend_output_max_chars: int = 20000
    raw_backend_output_redact: bool = True


@dataclass(frozen=True)
class ResearchConfig:
    """Top-level research configuration loaded from a YAML file.

    Attributes:
        topic: The research question.
        goal: Description of the desired deliverable.
        dimensions: Tuple of dimensions to explore.
        scoring: Scoring parameters.
        execution: Execution / runtime parameters.
        security: Security policy for the run.
    """

    topic: str
    goal: str
    dimensions: tuple[str, ...]
    methodology: MethodologyConfig = field(default_factory=MethodologyConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    hitl: HitlConfig = field(default_factory=HitlConfig)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "ResearchConfig":
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
            review_type=methodology_raw.get("review_type", ""),
            inclusion_criteria=tuple(methodology_raw.get("inclusion_criteria", [])),
            exclusion_criteria=tuple(methodology_raw.get("exclusion_criteria", [])),
            search_sources=tuple(methodology_raw.get("search_sources", [])),
            stopping_criteria=tuple(methodology_raw.get("stopping_criteria", [])),
            stopping_rationale=methodology_raw.get("stopping_rationale", ""),
            scoring_rationale=methodology_raw.get("scoring_rationale", ""),
            preferred_source_types=tuple(methodology_raw.get("preferred_source_types", [])),
            recency_days=methodology_raw.get("recency_days", 0),
        )

        # --- Evaluation -------------------------------------------------------
        evaluation_raw: dict[str, Any] = research.get("evaluation", {})
        judges_raw = evaluation_raw.get("judges", [])
        judges: list[JudgeConfig] = []
        for j in judges_raw:
            if not isinstance(j, dict) or "adapter" not in j:
                continue
            judges.append(JudgeConfig(
                adapter=str(j["adapter"]),
                model=str(j.get("model", "")),
                weight=float(j.get("weight", 1.0)),
            ))
        evaluation = EvaluationConfig(
            benchmark_id=evaluation_raw.get("benchmark_id", ""),
            run_baselines=evaluation_raw.get("run_baselines", False),
            expected_dimensions=tuple(evaluation_raw.get("expected_dimensions", [])),
            required_keywords=tuple(evaluation_raw.get("required_keywords", [])),
            reference_runs=tuple(evaluation_raw.get("reference_runs", [])),
            semantic_calibration=evaluation_raw.get("semantic_calibration", True),
            semantic_review=evaluation_raw.get("semantic_review", False),
            judges=tuple(judges),
            judge_disagreement_threshold=int(
                evaluation_raw.get("judge_disagreement_threshold", 2)
            ),
        )

        # --- Reporting --------------------------------------------------------
        reporting_raw: dict[str, Any] = research.get("reporting", {})
        raw_backend_output_max_chars = reporting_raw.get("raw_backend_output_max_chars", 20000)
        if raw_backend_output_max_chars <= 0:
            raise ValueError(
                f"raw_backend_output_max_chars must be positive, got {raw_backend_output_max_chars}"
            )
        output_style = reporting_raw.get("output_style", "default")
        if output_style not in VALID_OUTPUT_STYLES:
            raise ValueError(
                f"Invalid reporting.output_style '{output_style}'. "
                f"Must be one of: {', '.join(VALID_OUTPUT_STYLES)}"
            )
        style_overrides_raw: dict[str, Any] = reporting_raw.get("style_overrides", {})
        recommendation_mode = style_overrides_raw.get("recommendation_mode", "")
        if recommendation_mode not in ("", "ranked", "decision_only"):
            raise ValueError(
                "Invalid reporting.style_overrides.recommendation_mode "
                f"'{recommendation_mode}'. Must be one of: ranked, decision_only"
            )
        citation_mode = style_overrides_raw.get("citation_mode", "")
        if citation_mode not in ("", "inline_links", "references_section"):
            raise ValueError(
                "Invalid reporting.style_overrides.citation_mode "
                f"'{citation_mode}'. Must be one of: inline_links, references_section"
            )
        section_order = style_overrides_raw.get("section_order", "")
        if section_order not in ("", "standard", "recommendation_first", "evidence_first"):
            raise ValueError(
                "Invalid reporting.style_overrides.section_order "
                f"'{section_order}'. Must be one of: standard, recommendation_first, evidence_first"
            )
        reporting = ReportingConfig(
            export_html=reporting_raw.get("export_html", True),
            export_pdf=reporting_raw.get("export_pdf", False),
            report_title=reporting_raw.get("report_title", ""),
            output_style=output_style,
            style_overrides=OutputStyleOverrides(
                include_executive_summary=style_overrides_raw.get("include_executive_summary"),
                include_comparison_table=style_overrides_raw.get("include_comparison_table"),
                include_methodology=style_overrides_raw.get("include_methodology"),
                include_limitations=style_overrides_raw.get("include_limitations"),
                include_next_actions=style_overrides_raw.get("include_next_actions"),
                section_order=section_order,
                recommendation_mode=recommendation_mode,
                citation_mode=citation_mode,
            ),
            capture_raw_backend_outputs=reporting_raw.get("capture_raw_backend_outputs", False),
            raw_backend_output_max_chars=raw_backend_output_max_chars,
            raw_backend_output_redact=reporting_raw.get("raw_backend_output_redact", True),
        )

        # --- Scoring ----------------------------------------------------------
        scoring_raw: dict[str, Any] = research.get("scoring", {})
        evidence = scoring_raw.get("evidence_types")
        scoring_defaults = ScoringConfig()
        weights_raw: dict[str, Any] = scoring_raw.get("weights", {})
        weights_defaults = ScoringWeights()
        weights = ScoringWeights(
            coverage_weight=float(weights_raw.get("coverage_weight", weights_defaults.coverage_weight)),
            quality_weight=float(weights_raw.get("quality_weight", weights_defaults.quality_weight)),
            novelty_weight=float(weights_raw.get("novelty_weight", weights_defaults.novelty_weight)),
            judge_novelty_share=float(weights_raw.get("judge_novelty_share", weights_defaults.judge_novelty_share)),
            depth_bonus=float(weights_raw.get("depth_bonus", weights_defaults.depth_bonus)),
        )
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
            weights=weights,
        )

        # --- Discovery (gap intake filtering) ---------------------------------
        discovery_raw: dict[str, Any] = research.get("discovery", {})
        discovery_defaults = DiscoveryConfig()
        discovery = DiscoveryConfig(
            language_filter=discovery_raw.get(
                "language_filter", discovery_defaults.language_filter
            ),
            dedupe_threshold=float(
                discovery_raw.get("dedupe_threshold", discovery_defaults.dedupe_threshold)
            ),
            promotion_enabled=bool(
                discovery_raw.get("promotion_enabled", discovery_defaults.promotion_enabled)
            ),
            promotion_min_occurrences=int(
                discovery_raw.get("promotion_min_occurrences", discovery_defaults.promotion_min_occurrences)
            ),
            promotion_high_confidence=int(
                discovery_raw.get("promotion_high_confidence", discovery_defaults.promotion_high_confidence)
            ),
        )

        # --- Execution --------------------------------------------------------
        exec_raw: dict[str, Any] = research.get("execution", {})
        exec_defaults = ExecutionConfig()
        providers = _parse_providers_config(exec_raw.get("providers", {}))

        backend = exec_raw.get("backend", exec_defaults.backend)
        if backend not in VALID_BACKENDS:
            raise ValueError(
                f"Invalid backend '{backend}'. Must be one of: {', '.join(VALID_BACKENDS)}"
            )

        model = exec_raw.get("model", exec_defaults.model)

        max_budget = exec_raw.get("max_budget_per_call", exec_defaults.max_budget_per_call)
        if max_budget < 0:
            raise ValueError(f"max_budget_per_call must be non-negative, got {max_budget}")

        retry_api_errors = exec_raw.get("retry_api_errors", exec_defaults.retry_api_errors)
        if retry_api_errors < 0:
            raise ValueError(f"retry_api_errors must be non-negative, got {retry_api_errors}")

        retry_backoff_seconds = exec_raw.get("retry_backoff_seconds", exec_defaults.retry_backoff_seconds)
        if retry_backoff_seconds <= 0:
            raise ValueError(f"retry_backoff_seconds must be positive, got {retry_backoff_seconds}")

        timeout = exec_raw.get("timeout_seconds", exec_defaults.timeout_seconds)
        if timeout <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {timeout}")

        preflight_timeout = exec_raw.get(
            "backend_preflight_timeout_seconds",
            exec_defaults.backend_preflight_timeout_seconds,
        )
        if preflight_timeout <= 0:
            raise ValueError(
                f"backend_preflight_timeout_seconds must be positive, got {preflight_timeout}"
            )

        # --- Strategy / multi-backend -----------------------------------------
        strategy = exec_raw.get("strategy", "single")
        if strategy not in VALID_STRATEGIES:
            raise ValueError(
                f"Invalid strategy '{strategy}'. Must be one of: {', '.join(VALID_STRATEGIES)}"
            )

        backends_raw: dict[str, Any] = exec_raw.get("backends", {})
        if providers:
            if backends_raw:
                research_val = backends_raw.get("research", [backends_raw.get("primary", next(iter(providers)))])
                if isinstance(research_val, str):
                    research_val = [research_val]
                backends_config = BackendsConfig(
                    primary=backends_raw.get("primary", next(iter(providers))),
                    research=tuple(research_val),
                    judge=backends_raw.get("judge", ""),
                    utility=backends_raw.get("utility", ""),
                )
            else:
                first_provider = next(iter(providers))
                backends_config = BackendsConfig(primary=first_provider, research=(first_provider,))
            _validate_provider_references(backends_config, providers)
        elif backends_raw:
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
        strategy_config = _build_strategy_config_from_raw(strat_raw)

        execution = ExecutionConfig(
            max_iterations=exec_raw.get("max_iterations", exec_defaults.max_iterations),
            compress_every=exec_raw.get("compress_every", exec_defaults.compress_every),
            system_prompt=exec_raw.get("system_prompt", exec_defaults.system_prompt),
            stream=exec_raw.get("stream", exec_defaults.stream),
            retry_api_errors=retry_api_errors,
            retry_backoff_seconds=retry_backoff_seconds,
            allowed_tools=exec_raw.get("allowed_tools", exec_defaults.allowed_tools),
            max_turns=exec_raw.get("max_turns", exec_defaults.max_turns),
            timeout_seconds=timeout,
            backend=backend,
            model=model,
            max_budget_per_call=max_budget,
            backend_preflight=exec_raw.get("backend_preflight", exec_defaults.backend_preflight),
            backend_preflight_timeout_seconds=preflight_timeout,
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

        # --- Security ---------------------------------------------------------
        security_raw: dict[str, Any] = research.get("security", {})
        security = _parse_security_config(security_raw)

        # --- HITL policy ------------------------------------------------------
        hitl_raw: dict[str, Any] = research.get("hitl", {})
        hitl = _parse_hitl_config(hitl_raw)

        return cls(
            topic=research["topic"],
            goal=research.get("goal", research["topic"]),
            dimensions=tuple(research.get("dimensions", [])),
            methodology=methodology,
            evaluation=evaluation,
            reporting=reporting,
            scoring=scoring,
            discovery=discovery,
            execution=execution,
            security=security,
            hitl=hitl,
            providers=providers,
        )
