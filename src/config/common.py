"""Shared config types and parsing helpers used across all workflow modes.

Holds the dataclasses every workflow (research, refine, plan, implement)
composes — provider/backend wiring, strategy settings, execution params —
and the YAML parsers that build them. Workflow-specific modules
(research.py, document.py, plan.py) import from here; this module does
NOT import from any workflow submodule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..backends import VALID_BACKENDS

# Valid multi-backend strategy names.
VALID_STRATEGIES = ("single", "ensemble", "adversarial", "parallel", "serial", "specialist")


def _validate_backend_name(name: str, role: str) -> None:
    """Raise ``ValueError`` when *name* is not a known backend."""
    if name not in VALID_BACKENDS:
        raise ValueError(
            f"Invalid {role} backend '{name}'. Must be one of: {', '.join(VALID_BACKENDS)}"
        )


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderConfig:
    """Named provider instance configuration."""

    adapter: str
    model: str = ""
    base_url: str = ""
    api_version: str = ""
    region: str = ""
    organization: str = ""
    aws_profile: str = ""
    allowed_tools: str = ""
    max_turns: int = 0
    timeout_seconds: int = 0
    max_budget_per_call: float = -1.0


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

    primary: str = "claude-cli"
    research: tuple[str, ...] = ("claude-cli",)
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
class ExecutionConfig:
    """Runtime parameters for the research loop.

    Attributes:
        max_iterations: Maximum iterations before stopping.  ``0`` means
            infinite (run until interrupted).
        compress_every: Compress the knowledge base every *N* iterations.
        system_prompt: Optional shared system/developer instruction.
        stream: Enable live backend streaming for research-phase calls when the
            selected backend supports it.
        retry_api_errors: Maximum retry attempts for retryable non-streaming
            API backend failures. Tool loops and streaming calls are excluded.
        retry_backoff_seconds: Base retry delay in seconds for retryable API
            failures; subsequent retries apply exponential backoff.
        allowed_tools: Comma-separated list of tools available to the agent.
        max_turns: Maximum agent turns per CLI invocation.
        timeout_seconds: Per-invocation timeout in seconds.
        backend: CLI backend to use (``"claude-cli"``, ``"codex-cli"``, ``"gemini-cli"``,
            or ``"copilot-cli"``).
        model: Model name (backend-specific, e.g. ``"sonnet"`` for Claude).
        max_budget_per_call: USD cap per CLI invocation (backends that don't
            support per-call budgets ignore this).
        backend_preflight: Run a cheap live "OK" probe for CLI backends before
            starting a non-dry-run workflow.
        backend_preflight_timeout_seconds: Timeout for each CLI preflight probe.
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
    system_prompt: str = ""
    stream: bool = False
    retry_api_errors: int = 0
    retry_backoff_seconds: float = 1.0
    allowed_tools: str = "WebSearch,WebFetch,Read,Bash,Glob,Grep"
    max_turns: int = 10
    timeout_seconds: int = 600
    backend: str = "claude-cli"
    model: str = "sonnet"
    max_budget_per_call: float = 0.50
    backend_preflight: bool = True
    backend_preflight_timeout_seconds: int = 60
    lightweight_mode: bool = False
    isolate_backend_context: bool = True
    sanitize_backend_env: bool = True
    strategy: str = "single"
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)


# ── Parsers ───────────────────────────────────────────────────────────────────


def _parse_providers_config(raw: dict[str, Any]) -> dict[str, ProviderConfig]:
    """Parse named provider instances."""
    providers: dict[str, ProviderConfig] = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Provider '{name}' must be a mapping")
        adapter = entry.get("adapter", "")
        if adapter not in VALID_BACKENDS:
            raise ValueError(
                f"Invalid provider adapter '{adapter}' for provider '{name}'. "
                f"Must be one of: {', '.join(VALID_BACKENDS)}"
            )
        providers[name] = ProviderConfig(
            adapter=adapter,
            model=entry.get("model", ""),
            base_url=entry.get("base_url", ""),
            api_version=str(entry.get("api_version", "")),
            region=entry.get("region", ""),
            organization=entry.get("organization", ""),
            aws_profile=entry.get("aws_profile", ""),
            allowed_tools=entry.get("allowed_tools", ""),
            max_turns=entry.get("max_turns", 0),
            timeout_seconds=entry.get("timeout_seconds", 0),
            max_budget_per_call=entry.get("max_budget_per_call", -1.0),
        )
    return providers


def _validate_provider_references(backends: BackendsConfig, providers: dict[str, ProviderConfig]) -> None:
    """Validate that role mappings point to defined provider instances."""
    if not providers:
        return
    for name in backends.all_backend_names():
        if name not in providers:
            raise ValueError(f"Unknown provider instance '{name}' referenced in backends")


def _parse_backends_config(raw: dict[str, Any], *, default_primary: str = "claude-cli") -> BackendsConfig:
    """Parse and validate a ``backends:`` mapping."""
    if not raw:
        return BackendsConfig(primary=default_primary, research=(default_primary,))

    research_val = raw.get("research", [raw.get("primary", default_primary)])
    if isinstance(research_val, str):
        research_val = [research_val]

    primary = raw.get("primary", default_primary)
    _validate_backend_name(primary, "primary")
    for name in research_val:
        _validate_backend_name(name, "research")

    judge = raw.get("judge", "")
    if judge:
        _validate_backend_name(judge, "judge")

    utility = raw.get("utility", "")
    if utility:
        _validate_backend_name(utility, "utility")

    return BackendsConfig(
        primary=primary,
        research=tuple(research_val),
        judge=judge,
        utility=utility,
    )


def _build_strategy_config_from_raw(strat_raw: dict[str, Any]) -> StrategyConfig:
    """Build a typed StrategyConfig from a raw mapping, applying typed defaults."""
    return StrategyConfig(
        merge_mode=strat_raw.get("merge_mode", "best"),
        merge_threshold=strat_raw.get("merge_threshold", 40.0),
        critique_depth=strat_raw.get("critique_depth", "standard"),
        refiner_sees_draft=strat_raw.get("refiner_sees_draft", True),
        max_parallel=strat_raw.get("max_parallel", 3),
        stagger_seconds=strat_raw.get("stagger_seconds", 5),
    )


def _build_backends_config_from_raw(
    backends_raw: dict[str, Any], *, default_backend: str
) -> BackendsConfig:
    """Build a typed BackendsConfig from a raw {primary, research, judge, utility}
    mapping, validating every role against VALID_BACKENDS.

    Used by non-research workflows (Document, Plan, Implement) where backend
    role assignment doesn't go through a provider-instance indirection.
    ResearchConfig has its own provider-aware path and does not call this.
    """
    research_val = backends_raw.get("research", [default_backend])
    if isinstance(research_val, str):
        research_val = [research_val]
    for name in research_val:
        _validate_backend_name(name, "research")

    primary = backends_raw.get("primary", default_backend)
    _validate_backend_name(primary, "primary")

    judge = backends_raw.get("judge", "")
    if judge:
        _validate_backend_name(judge, "judge")

    utility = backends_raw.get("utility", "")
    if utility:
        _validate_backend_name(utility, "utility")

    return BackendsConfig(
        primary=primary,
        research=tuple(research_val),
        judge=judge,
        utility=utility,
    )


def _resolve_backends_and_providers(
    raw_section: dict[str, Any],
) -> tuple[dict[str, ProviderConfig], BackendsConfig]:
    """Common provider + backends resolution for Document/Plan workflows.

    When the YAML section has a ``providers:`` block, ``backends:`` keys
    refer to provider-instance names (the indirection layer) and we don't
    apply ``VALID_BACKENDS`` validation against role names — that check
    runs against the provider adapters inside ``_parse_providers_config``.
    When there is no ``providers:`` block, ``backends:`` keys refer
    directly to adapter names and we validate them via ``_parse_backends_config``.

    ResearchConfig has its own slightly different variant (emits a warning
    when judge is also a research backend); this helper is for the simpler
    Document and Plan workflows that used to carry byte-identical copies
    of this block.
    """
    providers = _parse_providers_config(raw_section.get("providers", {}))
    if providers:
        backends_raw = raw_section.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get(
                "research", [backends_raw.get("primary", next(iter(providers)))]
            )
            if isinstance(research_val, str):
                research_val = [research_val]
            backends_cfg = BackendsConfig(
                primary=backends_raw.get("primary", next(iter(providers))),
                research=tuple(research_val),
                judge=backends_raw.get("judge", ""),
                utility=backends_raw.get("utility", ""),
            )
        else:
            first_provider = next(iter(providers))
            backends_cfg = BackendsConfig(primary=first_provider, research=(first_provider,))
        _validate_provider_references(backends_cfg, providers)
    else:
        backends_cfg = _parse_backends_config(raw_section.get("backends", {}))
    return providers, backends_cfg


def _parse_execution_config(raw: dict[str, Any]) -> ExecutionConfig:
    """Parse the shared execution settings used by all workflows.

    Performs the same validation that ``ResearchConfig.from_yaml`` performs
    inline — backend name + strategy name against the valid-value sets, and
    builds typed ``BackendsConfig`` / ``StrategyConfig`` objects rather than
    passing raw dicts through to fields the dataclass declares as typed
    (which used to slip past at construction time and AttributeError later
    on first read).
    """
    exec_defaults = ExecutionConfig()
    timeout = raw.get("timeout_seconds", exec_defaults.timeout_seconds)
    if timeout <= 0:
        raise ValueError(f"timeout_seconds must be positive, got {timeout}")

    preflight_timeout = raw.get(
        "backend_preflight_timeout_seconds",
        exec_defaults.backend_preflight_timeout_seconds,
    )
    if preflight_timeout <= 0:
        raise ValueError(
            f"backend_preflight_timeout_seconds must be positive, got {preflight_timeout}"
        )

    max_budget = raw.get("max_budget_per_call", exec_defaults.max_budget_per_call)
    if max_budget < 0:
        raise ValueError(f"max_budget_per_call must be non-negative, got {max_budget}")

    retry_api_errors = raw.get("retry_api_errors", exec_defaults.retry_api_errors)
    if retry_api_errors < 0:
        raise ValueError(f"retry_api_errors must be non-negative, got {retry_api_errors}")

    retry_backoff_seconds = raw.get("retry_backoff_seconds", exec_defaults.retry_backoff_seconds)
    if retry_backoff_seconds <= 0:
        raise ValueError(f"retry_backoff_seconds must be positive, got {retry_backoff_seconds}")

    backend = raw.get("backend", exec_defaults.backend)
    _validate_backend_name(backend, "primary")

    strategy = raw.get("strategy", exec_defaults.strategy)
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: {', '.join(VALID_STRATEGIES)}"
        )

    backends_raw = raw.get("backends", {})
    if isinstance(backends_raw, dict) and backends_raw:
        backends_config = _build_backends_config_from_raw(
            backends_raw, default_backend=backend
        )
    else:
        backends_config = BackendsConfig(primary=backend, research=(backend,))

    strat_raw = raw.get("strategy_config", {})
    strategy_config = _build_strategy_config_from_raw(
        strat_raw if isinstance(strat_raw, dict) else {}
    )

    model = raw.get("model", exec_defaults.model)

    return ExecutionConfig(
        max_iterations=raw.get("max_iterations", exec_defaults.max_iterations),
        compress_every=raw.get("compress_every", exec_defaults.compress_every),
        system_prompt=raw.get("system_prompt", exec_defaults.system_prompt),
        stream=raw.get("stream", exec_defaults.stream),
        retry_api_errors=retry_api_errors,
        retry_backoff_seconds=retry_backoff_seconds,
        allowed_tools=raw.get("allowed_tools", exec_defaults.allowed_tools),
        max_turns=raw.get("max_turns", exec_defaults.max_turns),
        timeout_seconds=timeout,
        backend=backend,
        model=model,
        max_budget_per_call=max_budget,
        backend_preflight=raw.get("backend_preflight", exec_defaults.backend_preflight),
        backend_preflight_timeout_seconds=preflight_timeout,
        lightweight_mode=raw.get("lightweight_mode", exec_defaults.lightweight_mode),
        isolate_backend_context=raw.get(
            "isolate_backend_context",
            exec_defaults.isolate_backend_context,
        ),
        sanitize_backend_env=raw.get(
            "sanitize_backend_env",
            exec_defaults.sanitize_backend_env,
        ),
        strategy=strategy,
        backends=backends_config,
        strategy_config=strategy_config,
    )
