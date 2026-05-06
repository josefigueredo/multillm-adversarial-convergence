"""Autonomous research loop powered by AI coding agent CLIs.

Implements the Karpathy autoresearch pattern: an infinite loop of
hypothesis generation, research execution, scoring, and keep/discard
decisions.  Each iteration invokes a configurable CLI backend in
headless mode.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import CLAUDE_SHORTNAMES, AgentResponse, Backend, CallOptions, StreamEvent, get_backends
from .backend_options import apply_backend_capabilities, build_call_options
from .audit_trail import AuditTrailWriter
from .artifacts import (
    cli_version,
    dashboard_payload,
    effective_config_payload,
    git_commit,
    load_json_if_exists,
    metrics_payload,
    package_version,
    run_manifest_payload,
    write_dashboard,
    write_effective_config,
    write_html_report,
    write_pdf_report,
    write_portfolio,
)
from .agreement_artifacts import write_agreement_artifact
from .config import ProviderConfig, ResearchConfig
from .constraints import (
    format_results_table,
    goal_constraints_summary,
    is_lightweight_mode,
    postprocess_goal_output,
    synthesis_knowledge_context,
    synthesis_results_summary,
)
from .comparison import benchmark_summary, reference_run_comparison
from .evaluation_artifacts import write_evaluation_artifacts
from .output_style import build_output_style_contract
from .evidence.provenance import (
    extract_citations,
    extract_claims,
)
from .prompts import render as _render
from . import research_loop as loop_mod
from .pdf_report import render_simple_pdf
from .portfolio import build_portfolio, render_portfolio_html
from .evidence.provenance_artifacts import write_provenance_artifacts_bundle
from .evidence.references import build_references_section, inject_references_section
from .workflows.research_states import ResearchState
from .workflows.transitions import WorkflowTransitionEmitter
from .reporting import render_html_report as render_html_report_fn
from .deliverables.report_exports import write_reporting_artifacts
from .reproducibility import write_prompt_snapshot, write_rerun_script
from .run_finalize import finalize_run_artifacts
from .run_io import setup_output_dir, write_results_header
from .run_metadata_artifacts import write_run_metadata_artifacts
from .run_paths import RunPaths
from .run_state import UsageTotals, resume_state, track_candidate_usage, track_cost, track_usage
from .runtime_telemetry import accumulate_retries, accumulate_tool_loop
from .evidence.provenance_pipeline import build_provenance_bundle
from .semantic_eval import (
    semantic_calibration,
    semantic_review_disabled,
    semantic_review_empty,
    semantic_review_fallback,
    semantic_review_from_payload,
)
from .strategy import ResearchCandidate, Strategy, get_strategy
from .policy.tool_runtime import run_function_tool_loop
from .policy.sandbox_executor import SandboxExecutor
from .sandbox import select_sandbox_backend
from .policy.security_runtime import resolve_runtime_security_policy
from .policy.policy_denial import PolicyDeniedError
from .policy.tool_capabilities import classify_allowed_tools

log = logging.getLogger("autoresearch")

KB_MAX_WORDS = 4000
LIGHTWEIGHT_KB_WORDS = 800


# ---------------------------------------------------------------------------
# AutoResearcher
# ---------------------------------------------------------------------------

class AutoResearcher:
    """Autonomous research loop.

    Mirrors Karpathy's autoresearch pattern:
    Hypothesis -> Execute -> Score -> Keep/Revert -> Log -> Repeat.

    Supports multi-backend strategies: each research phase can use a
    different backend, and the execution phase can run in parallel
    across backends.

    Args:
        config: Research configuration.
        backend: Default CLI backend (used when strategy is ``"single"``).
        output_dir: Directory for all output artifacts.
        backends: Optional pre-built backend instances (keyed by name).
            If ``None``, built from config.
        strategy: Optional pre-built strategy.  If ``None``, built from config.
    """

    MAX_ATTEMPTS_PER_DIMENSION = 3

    def __init__(
        self,
        config: ResearchConfig,
        backend: Backend,
        output_dir: Path,
        backends: dict[str, Backend] | None = None,
        strategy: Strategy | None = None,
        resume: bool = False,
        config_path: Path | None = None,
    ) -> None:
        self.config = config
        self.backend = backend  # kept for backward compat + summary
        self.resume = resume
        self.config_path = config_path
        self.output_dir = output_dir
        self.paths = RunPaths.for_output_dir(output_dir)
        self.iterations_dir = self.paths.iterations_dir
        self.results_path = self.paths.results
        self.kb_path = self.paths.knowledge_base
        self.synthesis_path = self.paths.synthesis
        self.methods_path = self.paths.methods
        self.run_log_path = self.paths.run_log
        self.audit_trail_path = self.paths.audit_trail
        self.manifest_path = self.paths.manifest
        self.metrics_path = self.paths.metrics
        self.claims_path = self.paths.claims
        self.citations_path = self.paths.citations
        self.evidence_links_path = self.paths.evidence_links
        self.evidence_quality_path = self.paths.evidence_quality
        self.rubric_path = self.paths.rubric
        self.contradictions_path = self.paths.contradictions
        self.certainty_tables_path = self.paths.certainty_tables
        self.search_log_path = self.paths.search_log
        self.screening_log_path = self.paths.screening_log
        self.baseline_path = self.paths.baseline
        self.evaluation_path = self.paths.evaluation
        self.comparison_path = self.paths.comparison
        self.strategy_summary_path = self.paths.strategy_summary
        self.dashboard_path = self.paths.dashboard
        self.semantic_calibration_path = self.paths.semantic_calibration
        self.semantic_review_path = self.paths.semantic_review
        self.tool_trace_path = self.paths.tool_trace
        self.prompt_snapshot_path = self.paths.prompt_snapshot
        self.rerun_script_path = self.paths.rerun_script
        self.report_html_path = self.paths.report_html
        self.report_pdf_path = self.paths.report_pdf
        self.portfolio_path = self.paths.portfolio
        self.portfolio_html_path = self.paths.portfolio_html

        # Multi-backend support
        if backends is None:
            all_names = config.execution.backends.all_backend_names()
            self.backends = get_backends(all_names)
        else:
            self.backends = backends

        if strategy is None:
            self.strategy = get_strategy(
                config.execution.strategy,
                config.execution.backends,
                config.execution.strategy_config,
                self.backends,
            )
        else:
            self.strategy = strategy

        self.iteration: int = 0
        self.best_score: float = 0.0
        self.best_scores: dict[str, float] = {}
        self.knowledge_base: str = ""
        self.explored_dimensions: list[str] = []
        self.discovered_dimensions: list[str] = []
        # Discovery plan Phase 2: structured gap state alongside the
        # legacy bare-string list.  Lock-step updated via record_gap()
        # in the loop, persisted to discovered_gaps.json sidecar after
        # each iteration, restored on --resume from the sidecar (or
        # via legacy TSV fallback for runs that pre-date the schema).
        self.discovered_gaps: dict[str, Any] = {}
        self.total_cost: float = 0.0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.per_backend_costs: dict[str, float] = {}
        self.per_backend_tokens: dict[str, dict[str, int]] = {}
        self.results: list[dict[str, str]] = []
        self._dimension_attempts: dict[str, int] = {}
        self._run_started_at: str | None = None
        self._run_completed_at: str | None = None
        self._run_status: str = "initialized"
        self._current_workflow_state: ResearchState = ResearchState.IDLE
        self._claims: list[dict[str, Any]] = []
        self._citations: list[dict[str, Any]] = []
        self._candidate_assessments: list = []
        self._usage = UsageTotals()
        self._backend_workdir: Path | None = None
        self._sandbox: SandboxExecutor | None = None
        self._tool_loop_summary: dict[str, Any] = {
            "runs": 0,
            "tool_calls": 0,
            "tool_failures": 0,
            "per_backend": {},
            "per_tool": {},
        }
        self._retry_summary: dict[str, Any] = {
            "total_retries": 0,
            "per_backend": {},
            "per_category": {},
            "per_backend_category": {},
        }
        self._tool_trace: list[dict[str, Any]] = []
        self._prompt_snapshots: list[dict[str, Any]] = []
        # Cached most-recent IterationScore for dashboard breakdown
        # surfacing.  ``None`` until the first iteration completes.
        self._latest_score: Any = None
        self._audit_trail = AuditTrailWriter(self.audit_trail_path, mode="research", run_id=self.output_dir.name)

    def _sync_paths(self) -> None:
        """Recompute derived artifact paths from the current output directory."""
        self.paths = RunPaths.for_output_dir(self.output_dir)
        self.iterations_dir = self.paths.iterations_dir
        self.results_path = self.paths.results
        self.kb_path = self.paths.knowledge_base
        self.synthesis_path = self.paths.synthesis
        self.methods_path = self.paths.methods
        self.run_log_path = self.paths.run_log
        self.audit_trail_path = self.paths.audit_trail
        self.manifest_path = self.paths.manifest
        self.metrics_path = self.paths.metrics
        self.claims_path = self.paths.claims
        self.citations_path = self.paths.citations
        self.evidence_links_path = self.paths.evidence_links
        self.evidence_quality_path = self.paths.evidence_quality
        self.rubric_path = self.paths.rubric
        self.contradictions_path = self.paths.contradictions
        self.certainty_tables_path = self.paths.certainty_tables
        self.search_log_path = self.paths.search_log
        self.screening_log_path = self.paths.screening_log
        self.baseline_path = self.paths.baseline
        self.evaluation_path = self.paths.evaluation
        self.comparison_path = self.paths.comparison
        self.strategy_summary_path = self.paths.strategy_summary
        self.dashboard_path = self.paths.dashboard
        self.semantic_calibration_path = self.paths.semantic_calibration
        self.semantic_review_path = self.paths.semantic_review
        self.tool_trace_path = self.paths.tool_trace
        self.prompt_snapshot_path = self.paths.prompt_snapshot
        self.rerun_script_path = self.paths.rerun_script
        self.report_html_path = self.paths.report_html
        self.report_pdf_path = self.paths.report_pdf
        self.portfolio_path = self.paths.portfolio
        self.portfolio_html_path = self.paths.portfolio_html
        self._audit_trail = AuditTrailWriter(self.audit_trail_path, mode="research", run_id=self.output_dir.name)

    def _call(self, prompt: str, **kwargs: Any) -> AgentResponse:
        """Invoke the default backend with config defaults.

        For backward compatibility.  New code should use ``_call_with``.
        """
        backend = kwargs.pop("_backend", self.backend)
        return self._call_with(backend, prompt, **kwargs)

    @staticmethod
    def _resolve_model(backend: Backend, config_model: str) -> str:
        """Resolve model shortcuts into backend-safe model identifiers.

        Policy:
        - ``claude-cli`` accepts Claude shortnames directly.
        - direct providers may translate Claude shortnames to their own
          ``default_model`` when that mapping is well-defined.
        - aggregators must receive explicit model identifiers because silent
          translation hides routing semantics.
        """
        if config_model in CLAUDE_SHORTNAMES:
            if backend.name == "claude-cli":
                return config_model
            if backend.capabilities.provider_kind == "aggregator":
                raise ValueError(
                    f"Backend '{backend.name}' requires an explicit model identifier; "
                    f"shortname '{config_model}' is ambiguous for aggregators."
                )
            resolved = backend.capabilities.default_model
            if resolved:
                log.debug(
                    "Model '%s' not valid for %s, using '%s'.",
                    config_model, backend.name, resolved,
                )
                return resolved
        return config_model

    def _call_with(self, backend: Backend, prompt: str, **kwargs: Any) -> AgentResponse:
        """Invoke a specific backend with default options from config.

        Keyword arguments override the defaults from ``self.config.execution``.
        Automatically translates Claude model shortnames for non-Claude backends.

        When the sandbox is active (``tool_execution_mode: sandboxed`` +
        ``sandbox.mode: tool_calls``), the executor workspace is used as the
        process working directory and :meth:`SandboxExecutor.prepare_workspace`
        is called to ensure it exists.  For direct-mode runs the existing
        ``isolate_backend_context`` path is unchanged.
        """
        provider = getattr(backend, "provider_config", None)
        provider = provider if isinstance(provider, ProviderConfig) else None
        default_model = provider.model if provider is not None and provider.model else self.config.execution.model
        config_model = kwargs.pop("model", default_model)
        model = self._resolve_model(backend, config_model)
        isolated = self._should_isolate_backend(backend)

        # Determine working directory — sandbox workspace takes priority.
        sandbox = self._sandbox or self._make_transient_sandbox()
        process_env: dict[str, str] | None = None
        if sandbox.policy.sandbox_active:
            scope = self.config.security.sandbox.scope
            _iter = self.iteration if scope == "iteration" and self.iteration >= 1 else None
            sandbox.prepare_workspace(iteration=_iter)
            working_dir = str(sandbox.workspace_dir)
            process_env = sandbox.build_environment()
        elif isolated and self._backend_runtime_dir():
            working_dir = str(self._backend_runtime_dir())
        else:
            working_dir = ""

        opts = build_call_options(
            self.config.execution,
            provider=provider,
            working_directory=working_dir,
            sanitize_environment=isolated and self.config.execution.sanitize_backend_env,
        )
        opts = CallOptions(
            model=model,
            system_prompt=opts.system_prompt,
            stream=kwargs.pop("stream", False),
            tools=kwargs.pop("tools", ()),
            tool_choice=kwargs.pop("tool_choice", "auto"),
            allowed_tools=kwargs.pop("allowed_tools", opts.allowed_tools),
            max_turns=kwargs.pop("max_turns", opts.max_turns),
            max_budget_usd=kwargs.pop("max_budget_usd", opts.max_budget_usd),
            json_schema=opts.json_schema,
            working_directory=opts.working_directory,
            sanitize_environment=opts.sanitize_environment,
            process_env=process_env,
        )
        opts = apply_backend_capabilities(backend, opts)
        self._check_execution_policy(opts)
        self._record_prompt_snapshot(backend, prompt, opts)
        tool_registry = kwargs.pop("tool_registry", None)
        default_timeout = (
            provider.timeout_seconds
            if provider is not None and provider.timeout_seconds > 0
            else self.config.execution.timeout_seconds
        )
        timeout = kwargs.pop("timeout", default_timeout)
        if opts.tools:
            if opts.stream:
                return AgentResponse(
                    text="",
                    cost_usd=0.0,
                    is_error=True,
                    raw={
                        "error": {
                            "category": "tool_execution",
                            "message": "Function-tool execution is currently non-streaming only.",
                            "provider_code": "streaming_tool_calls_unsupported",
                            "retryable": False,
                        },
                        "payload": {},
                    },
                )
            if not tool_registry:
                return AgentResponse(
                    text="",
                    cost_usd=0.0,
                    is_error=True,
                    raw={
                        "error": {
                            "category": "tool_execution",
                            "message": "Function tools require a tool_registry for execution.",
                            "provider_code": "missing_tool_registry",
                            "retryable": False,
                        },
                        "payload": {},
                    },
                )
            return run_function_tool_loop(
                backend,
                prompt,
                opts,
                timeout=timeout,
                tool_registry=tool_registry,
            )
        if opts.stream and hasattr(backend, "invoke_stream"):
            return self._invoke_streaming_backend(backend, prompt, opts, timeout=timeout)
        return self._invoke_backend_with_retries(backend, prompt, opts, timeout=timeout)

    def _invoke_for_strategy(
        self,
        backend: Backend,
        prompt: str,
        *,
        allowed_tools: str = "",
        max_turns: int = 0,
        timeout: int = 0,
    ) -> AgentResponse:
        """Callback passed to strategies for backend invocation.

        Applies config defaults for any zero/empty values.
        """
        return self._call_with(
            backend,
            prompt,
            stream=self.config.execution.stream,
            allowed_tools=allowed_tools or "",
            max_turns=max_turns or self.config.execution.max_turns,
            timeout=timeout or self.config.execution.timeout_seconds,
        )

    def _invoke_streaming_backend(
        self,
        backend: Backend,
        prompt: str,
        opts: CallOptions,
        *,
        timeout: int,
    ) -> AgentResponse:
        """Render normalized streaming progress while preserving a final response."""
        events = backend.invoke_stream(prompt, opts, timeout=timeout)
        collected_text: list[str] = []
        completed_payload: dict[str, Any] | None = None
        error_payload: dict[str, Any] | None = None

        for event in events:
            self._print_stream_event(backend, event)
            if event.type == "text_delta" and event.text:
                collected_text.append(event.text)
            elif event.type == "completed":
                completed_payload = event.raw.get("response", event.raw)
            elif event.type == "error":
                error_payload = event.raw

        if error_payload:
            return AgentResponse(text="", cost_usd=0.0, is_error=True, raw={"stream_error": error_payload})

        if completed_payload and hasattr(backend, "parse_payload"):
            return backend.parse_payload(completed_payload)

        return AgentResponse(
            text="".join(collected_text),
            cost_usd=0.0,
            is_error=False,
            raw={"stream_completed": completed_payload or {}},
        )

    def _invoke_backend_with_retries(
        self,
        backend: Backend,
        prompt: str,
        opts: CallOptions,
        *,
        timeout: int,
    ) -> AgentResponse:
        """Invoke a backend with bounded retries for retryable API failures."""
        max_retries = max(0, int(self.config.execution.retry_api_errors))
        if backend.capabilities.transport != "api" or max_retries <= 0:
            return backend.invoke(prompt, opts, timeout=timeout)

        attempt = 0
        categories: dict[str, int] = {}
        while True:
            response = backend.invoke(prompt, opts, timeout=timeout)
            if not self._should_retry_response(response):
                if attempt > 0:
                    response.raw["retry_attempts"] = attempt
                    response.raw["retry_summary"] = {"categories": dict(categories)}
                return response
            category = self._response_error_category(response)
            if category:
                categories[category] = categories.get(category, 0) + 1
            if attempt >= max_retries:
                response.raw["retry_attempts"] = attempt
                response.raw["retry_summary"] = {"categories": dict(categories)}
                return response
            attempt += 1
            time.sleep(self.config.execution.retry_backoff_seconds * (2 ** (attempt - 1)))

    @staticmethod
    def _should_retry_response(response: AgentResponse) -> bool:
        """Return True when a response represents a retryable backend failure."""
        if not response.is_error or not isinstance(response.raw, dict):
            return False
        error = response.raw.get("error", {})
        if not isinstance(error, dict):
            return False
        return bool(error.get("retryable", False))

    @staticmethod
    def _response_error_category(response: AgentResponse) -> str:
        """Return normalized error category from a response when available."""
        if not isinstance(response.raw, dict):
            return ""
        error = response.raw.get("error", {})
        if not isinstance(error, dict):
            return ""
        return str(error.get("category", "") or "")

    @staticmethod
    def _print_stream_event(backend: Backend, event: StreamEvent) -> None:
        """Emit a compact streaming progress trace for interactive runs."""
        if event.type == "start":
            print(f"[{backend.name} stream] ", end="", flush=True)
            return
        if event.type == "text_delta" and event.text:
            print(event.text, end="", flush=True)
            return
        if event.type in {"completed", "error"}:
            print(flush=True)

    def _track_cost(self, cost: float, backend_name: str = "") -> None:
        """Add cost to totals (no token data available)."""
        track_cost(self._usage, cost, backend_name)
        self.total_cost = self._usage.total_cost
        self.per_backend_costs = self._usage.per_backend_costs

    def _track_usage(self, resp: AgentResponse, backend_name: str = "") -> None:
        """Add cost and token counts to totals and per-backend tracking."""
        track_usage(self._usage, resp, backend_name)
        self.total_cost = self._usage.total_cost
        self.total_input_tokens = self._usage.total_input_tokens
        self.total_output_tokens = self._usage.total_output_tokens
        self.per_backend_costs = self._usage.per_backend_costs
        self.per_backend_tokens = self._usage.per_backend_tokens
        self._track_retries(resp, backend_name)
        self._track_tool_loop(resp, backend_name)

    def _track_candidate_usage(self, candidate: ResearchCandidate) -> None:
        """Record usage for a strategy-produced research candidate."""
        track_candidate_usage(self._usage, candidate)
        self.total_cost = self._usage.total_cost
        self.total_input_tokens = self._usage.total_input_tokens
        self.total_output_tokens = self._usage.total_output_tokens
        self.per_backend_costs = self._usage.per_backend_costs
        self.per_backend_tokens = self._usage.per_backend_tokens

    def _track_tool_loop(self, resp: AgentResponse, backend_name: str = "") -> None:
        """Accumulate normalized tool-loop observability from responses."""
        accumulate_tool_loop(
            self._tool_loop_summary,
            self._tool_trace,
            resp,
            backend_name=backend_name,
        )

    def _track_retries(self, resp: AgentResponse, backend_name: str = "") -> None:
        """Accumulate retry counts from backend responses."""
        accumulate_retries(
            self._retry_summary,
            resp,
            backend_name=backend_name,
        )

    # -- Public API --------------------------------------------------------

    def run(self) -> None:
        """Start the research loop.  ``Ctrl+C`` triggers synthesis."""
        self._setup()
        if self.resume:
            self._resume()
        self._run_status = "running"
        self._record_event(
            "run_started",
            topic=self.config.topic,
            strategy=self.config.execution.strategy,
            resume=self.resume,
        )

        log.info(
            "Starting autoresearch [%s]: %s (%d dimensions configured)",
            self.strategy.describe(),
            self.config.topic,
            len(self.config.dimensions),
        )

        try:
            while True:
                if self._should_stop():
                    break
                self._run_iteration()
        except KeyboardInterrupt:
            log.info("Interrupted. Generating synthesis...")
            self._run_status = "interrupted"
            self._record_event("run_interrupted", iteration=self.iteration)
        except Exception as exc:
            self._run_status = "failed"
            self._record_event(
                "run_failed",
                iteration=self.iteration,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
        finally:
            if self._run_status == "running":
                self._run_status = "completed"
            _terminal = (
                ResearchState.CONVERGED
                if self._run_status == "completed"
                else ResearchState.INTERRUPTED
            )
            _emitter = WorkflowTransitionEmitter(
                self._audit_trail, "research", self._current_workflow_state
            )
            _emitter.transition(_terminal, iteration=self.iteration)
            self._current_workflow_state = _emitter.current_state
            self._generate_synthesis()
            self._generate_baseline()
            self._finalize_run_artifacts()
            self._record_event(
                "run_completed",
                iteration=self.iteration,
                status=self._run_status,
                explored_dimensions=len(self.explored_dimensions),
            )
            self._print_summary()

    def synthesize_only(self) -> None:
        """Generate a synthesis report from existing iteration data."""
        self._setup()
        self._resume()
        self._run_status = "synthesis_only"
        self._record_event("synthesis_only_started", iteration=self.iteration)
        self._generate_synthesis()
        self._generate_baseline()
        self._finalize_run_artifacts()
        self._record_event("synthesis_only_completed", iteration=self.iteration)

    def _should_stop(self) -> bool:
        """Return True when runtime stopping criteria have been met."""
        if 0 < self.config.execution.max_iterations <= self.iteration:
            log.info("Reached max_iterations=%d, stopping.", self.iteration)
            return True

        target = self.config.scoring.target_dimensions_total
        if target > 0 and len(self.explored_dimensions) >= target:
            log.info(
                "Reached target_dimensions_total=%d with %d explored dimensions, stopping.",
                target,
                len(self.explored_dimensions),
            )
            return True

        return False

    # -- Setup & resume ----------------------------------------------------

    def _setup(self) -> None:
        """Create output directories and initialise results.tsv if needed."""
        with self._audit_trail.step("setup_run", artifact_root=self.output_dir):
            self._sync_paths()
            setup_output_dir(self.output_dir, self.iterations_dir)
            self._ensure_backend_runtime_dir()
            if self._run_started_at is None:
                self._run_started_at = datetime.now(timezone.utc).isoformat()

            if not self.results_path.exists():
                self._write_tsv_header()
            self._write_methods()
            self._write_rerun_artifact()
            self._write_run_manifest()
            self._write_effective_config()
            _policy = resolve_runtime_security_policy(self.config.security, self.paths)
            _backend = select_sandbox_backend(self.config.security.sandbox, self.output_dir)
            self._sandbox = SandboxExecutor(_policy, _policy.workspace_dir, backend=_backend)
            _scope = self.config.security.sandbox.scope
            if _scope != "iteration":
                self._sandbox.prepare_workspace()
            self._audit_trail.emit(
                "sandbox_initialized",
                output_dir=str(self.paths.output_dir),
                workspace_dir=str(self._sandbox.workspace_dir),
            )
            self._audit_trail.emit(
                "sandbox_policy_applied",
                tool_execution_mode=_policy.tool_execution_mode,
                sandbox_active=_policy.sandbox_active,
                filesystem_access=_policy.filesystem_access,
                network_access=_policy.network_mode(),
                allow_host_bash=_policy.is_host_bash_allowed(),
            )

    def _resume(self) -> None:
        """Rebuild in-memory state from existing iteration files and TSV."""
        state = resume_state(
            iterations_dir=self.iterations_dir,
            results_path=self.results_path,
            knowledge_base_path=self.kb_path,
            configured_dimensions=self.config.dimensions,
            max_attempts_per_dimension=self.MAX_ATTEMPTS_PER_DIMENSION,
            discovered_gaps_sidecar=self.output_dir / "discovered_gaps.json",
        )
        if not state["iteration"]:
            return

        log.info("Resuming from %d existing iterations.", state["iteration"])
        self._record_event("run_resumed", iteration=state["iteration"])
        self.results = state["results"]
        self.best_score = state["best_score"]
        self.best_scores = state["best_scores"]
        self.explored_dimensions = state["explored_dimensions"]
        self.discovered_dimensions = state["discovered_dimensions"]
        self.discovered_gaps = state.get("discovered_gaps", {})
        self._dimension_attempts = state["dimension_attempts"]
        self.knowledge_base = state["knowledge_base"]
        self.iteration = state["iteration"]

        # Restore previously accumulated citations so that _generate_synthesis
        # can build a deterministic References section from prior iterations.
        if self.citations_path.exists():
            try:
                import json as _json
                self._citations = _json.loads(
                    self.citations_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass  # best-effort; synthesis will proceed with partial citations

    # -- Core loop ---------------------------------------------------------

    def _build_loop_context(self) -> "loop_mod.LoopContext":
        """Create the callback bundle for the research loop."""
        return loop_mod.LoopContext(
            config=self.config,
            strategy=self.strategy,
            call_with=self._call_with,
            invoke_for_strategy=self._invoke_for_strategy,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            track_candidate_usage=self._track_candidate_usage,
            collect_provenance=self._collect_provenance,
            methodology_summary=self._methodology_summary,
            kb_summary=self._kb_summary,
            format_dimension_list=self._format_dimension_list,
            goal_constraints_summary=self._goal_constraints_summary,
            audit_trail=self._audit_trail,
            artifact_root=self.output_dir,
        )

    def _build_loop_state(self) -> "loop_mod.LoopState":
        """Create a LoopState that shares mutable state with the orchestrator."""
        return loop_mod.LoopState(
            knowledge_base=self.knowledge_base,
            kb_path=self.kb_path,
            explored_dimensions=self.explored_dimensions,
            discovered_dimensions=self.discovered_dimensions,
            discovered_gaps=self.discovered_gaps,
            dimension_attempts=self._dimension_attempts,
            best_score=self.best_score,
            best_scores=self.best_scores,
            iteration=self.iteration,
            results=self.results,
            total_cost=self.total_cost,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            iterations_dir=self.iterations_dir,
            results_path=self.results_path,
            candidate_assessments=self._candidate_assessments,
            current_workflow_state=self._current_workflow_state,
        )

    def _sync_from_loop_state(self, state: "loop_mod.LoopState") -> None:
        """Copy mutable state back from the loop into the orchestrator."""
        self.knowledge_base = state.knowledge_base
        self.explored_dimensions = state.explored_dimensions
        self.discovered_dimensions = state.discovered_dimensions
        self.discovered_gaps = state.discovered_gaps
        self._dimension_attempts = state.dimension_attempts
        self.best_score = state.best_score
        self.best_scores = state.best_scores
        self.iteration = state.iteration
        self.results = state.results
        self._candidate_assessments = state.candidate_assessments
        self._current_workflow_state = state.current_workflow_state

    def _run_iteration(self) -> None:
        """Execute one full research iteration via the extracted loop module."""
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        if (
            self._sandbox is not None
            and self._sandbox.policy.sandbox_active
            and self.config.security.sandbox.scope == "iteration"
        ):
            next_iter = self.iteration + 1
            self._sandbox.prepare_workspace(iteration=next_iter)
            self._audit_trail.emit(
                "sandbox_workspace_prepared",
                iteration=next_iter,
                workspace_dir=str(self._sandbox.workspace_dir),
                scope="iteration",
            )
        loop_mod.run_iteration(ctx, state)
        self._sync_from_loop_state(state)

    def _record_event(self, event: str, **fields: Any) -> None:
        """Append one structured execution event to the run audit trail."""
        self._audit_trail.emit(event, **fields)

    # -- Loop shims (delegate to research_loop, retained for compatibility) --

    def _generate_hypothesis(self) -> dict[str, Any] | None:
        return loop_mod._generate_hypothesis(self._build_loop_context(), self._build_loop_state())

    def _execute_research(self, dimension: str, questions: list[str], approach: str) -> str:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._execute_research(ctx, state, dimension, questions, approach)

    def _select_candidate_findings(self, dimension: str, candidates: list) -> str:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._select_candidate_findings(ctx, state, dimension, candidates)

    def _score(self, dimension: str, findings: str):
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        return loop_mod._score(ctx, state, dimension, findings)

    def _merge_findings(self, dimension: str, findings: str, score) -> None:
        ctx = self._build_loop_context()
        state = self._build_loop_state()
        loop_mod._merge(ctx, state, dimension, findings, score)
        self._sync_from_loop_state(state)

    def _maybe_exhaust_dimension(self, dimension: str) -> None:
        state = self._build_loop_state()
        loop_mod._maybe_exhaust(state, dimension)
        self._sync_from_loop_state(state)

    def _save_iteration(self, dimension: str, findings: str, score, kept: bool) -> None:
        from .run_io import write_discovered_gaps_sidecar, write_iteration_markdown
        write_iteration_markdown(
            iterations_dir=self.iterations_dir, iteration=self.iteration,
            dimension=dimension, findings=findings, score=score, kept=kept,
        )
        # Cache the latest score so the dashboard can surface its breakdown.
        self._latest_score = score
        # Discovery plan Phase 2: persist the structured gap state so
        # --resume can restore it without re-deriving from results.tsv.
        if self.discovered_gaps:
            write_discovered_gaps_sidecar(self.output_dir, self.discovered_gaps)
        self._collect_provenance(findings, scope=f"iteration-{self.iteration:03d}", dimension=dimension)

    def _log_result(self, dimension: str, score, hypothesis: str, *, status: str) -> None:
        from .run_io import build_result_row, append_result_row
        row = build_result_row(
            iteration=self.iteration, dimension=dimension, score=score,
            hypothesis=hypothesis, status=status, total_cost_usd=self.total_cost,
            total_input_tokens=self.total_input_tokens, total_output_tokens=self.total_output_tokens,
        )
        self.results.append(row)
        append_result_row(self.results_path, row)

    def _write_tsv_header(self) -> None:
        """Write the header row to a new results.tsv file."""
        write_results_header(self.results_path)

    # -- Synthesis ---------------------------------------------------------

    def _generate_synthesis(self) -> None:
        """Generate a final synthesis report from the accumulated knowledge base."""
        if not self.knowledge_base:
            log.info("No knowledge base to synthesize.")
            return

        results_summary = self._synthesis_results_summary()
        knowledge_context = self._synthesis_knowledge_context()

        prompt = _render(
            "research_synthesize.md",
            topic=self.config.topic,
            goal=self.config.goal,
            methodology=self._methodology_summary(),
            output_style_contract=build_output_style_contract(
                self.config.reporting.output_style,
                self.config.reporting.style_overrides,
            ),
            goal_constraints=self._goal_constraints_summary(),
            lightweight_mode="yes" if self._is_lightweight_mode() else "no",
            knowledge_base=knowledge_context,
            results_summary=results_summary,
        )

        log.info("Generating final synthesis report...")
        synth_backend = self.strategy.get_synthesize_backend()
        with self._audit_trail.step(
            "generate_synthesis",
            artifact_root=self.output_dir,
            iteration=self.iteration,
            backend=synth_backend.name,
        ):
            resp = self._call_with(synth_backend, prompt, max_turns=5)
            self._track_usage(resp, synth_backend.name)

        if not resp.is_error and resp.text:
            final_text = self._postprocess_goal_output(resp.text)
            # Collect provenance from LLM-generated text before injecting
            # deterministic references (avoids re-extracting the injected URLs
            # as new citations and inflating provenance artifacts).
            self._collect_provenance(final_text, scope="synthesis")
            final_text = self._inject_deterministic_references(final_text)
            self.synthesis_path.write_text(final_text, encoding="utf-8")
            log.info("Synthesis saved to %s", self.synthesis_path)

    # -- Helpers -----------------------------------------------------------

    def _kb_summary(self) -> str:
        """Return a bounded summary of the knowledge base for prompt context.

        Uses a sandwich pattern: keeps early findings (context) plus
        the most recent findings (freshest data), truncating the middle.
        """
        if not self.knowledge_base:
            return "(No prior findings yet — this is the first iteration.)"
        words = self.knowledge_base.split()
        if len(words) <= KB_MAX_WORDS:
            return self.knowledge_base
        head_size = KB_MAX_WORDS // 3
        tail_size = KB_MAX_WORDS - head_size
        head = " ".join(words[:head_size])
        tail = " ".join(words[-tail_size:])
        return f"{head}\n\n[... {len(words) - KB_MAX_WORDS} words truncated ...]\n\n{tail}"

    def _format_dimension_list(self, dims: list[str]) -> str:
        """Format a list of dimensions as a markdown bullet list."""
        if not dims:
            return "(none)"
        return "\n".join(f"- {d}" for d in dims)

    def _methodology_summary(self) -> str:
        """Format methodology guidance for prompts and reporting."""
        methodology = self.config.methodology
        lines: list[str] = []
        if methodology.question:
            lines.append(f"- Question: {methodology.question}")
        if methodology.scope:
            lines.append(f"- Scope: {methodology.scope}")
        if methodology.review_type:
            lines.append(f"- Review type: {methodology.review_type}")
        if methodology.inclusion_criteria:
            lines.append("- Inclusion criteria:")
            lines.extend(f"  - {item}" for item in methodology.inclusion_criteria)
        if methodology.exclusion_criteria:
            lines.append("- Exclusion criteria:")
            lines.extend(f"  - {item}" for item in methodology.exclusion_criteria)
        if methodology.search_sources:
            lines.append("- Search sources:")
            lines.extend(f"  - {item}" for item in methodology.search_sources)
        if methodology.stopping_criteria:
            lines.append("- Stopping criteria:")
            lines.extend(f"  - {item}" for item in methodology.stopping_criteria)
        if methodology.stopping_rationale:
            lines.append(f"- Stopping rationale: {methodology.stopping_rationale}")
        if methodology.scoring_rationale:
            lines.append(f"- Scoring rationale: {methodology.scoring_rationale}")
        if methodology.preferred_source_types:
            lines.append("- Preferred source types:")
            lines.extend(f"  - {item}" for item in methodology.preferred_source_types)
        if methodology.recency_days > 0:
            lines.append(f"- Prefer sources from the last {methodology.recency_days} days for unstable facts.")
        return "\n".join(lines) if lines else "(No explicit methodology constraints.)"

    def _ensure_backend_runtime_dir(self) -> None:
        """Create a neutral working directory for backend subprocesses when enabled."""
        if not self.config.execution.isolate_backend_context:
            return
        if self._backend_workdir is None:
            self._backend_workdir = Path(tempfile.mkdtemp(prefix="autoresearch-backend-"))

    def _backend_runtime_dir(self) -> Path | None:
        """Return the isolated backend working directory, if enabled."""
        if not self.config.execution.isolate_backend_context:
            return None
        self._ensure_backend_runtime_dir()
        return self._backend_workdir

    def _should_isolate_backend(self, backend: Backend) -> bool:
        """Return True when backend-context isolation should be applied."""
        return self.config.execution.isolate_backend_context

    def _is_lightweight_mode(self) -> bool:
        """Return True when the run should optimize for brevity and low overhead."""
        return is_lightweight_mode(
            explicit_enabled=self.config.execution.lightweight_mode,
            goal=self.config.goal,
            topic=self.config.topic,
        )

    def _goal_constraints_summary(self) -> str:
        """Extract explicit deliverable constraints from the goal text."""
        return goal_constraints_summary(self.config.goal, lightweight_mode=self._is_lightweight_mode())

    def _postprocess_goal_output(self, text: str) -> str:
        """Deterministically repair short-form outputs to obey explicit goal constraints."""
        return postprocess_goal_output(text, goal=self.config.goal)

    def _inject_deterministic_references(self, text: str) -> str:
        """Append a deterministic References section built from tracked citations.

        Only applied for ``paper`` output style — other styles have their own
        community conventions and should not have a References block forced in.
        Returns *text* unchanged when the output style is not ``paper`` or when
        there are no URL-bearing citations to inject.
        """
        if self.config.reporting.output_style != "paper":
            return text
        refs_block = build_references_section(self._citations)
        return inject_references_section(text, refs_block)

    def _synthesis_knowledge_context(self) -> str:
        """Return the knowledge context to send to synthesis."""
        return synthesis_knowledge_context(
            self.knowledge_base,
            lightweight_mode=self._is_lightweight_mode(),
            lightweight_kb_words=LIGHTWEIGHT_KB_WORDS,
        )

    def _synthesis_results_summary(self) -> str:
        """Return a run summary tailored for synthesis prompting."""
        return synthesis_results_summary(self.results, lightweight_mode=self._is_lightweight_mode())

    def _format_results_table(self) -> str:
        """Format the results log as a markdown table for synthesis prompts."""
        return format_results_table(self.results)

    def _write_methods(self) -> None:
        """Write a human-readable methods artifact for the run."""
        content = (
            f"# Research Methods\n\n"
            f"## Goal\n\n{self.config.goal}\n\n"
            f"## Topic\n\n{self.config.topic}\n\n"
            f"## Methodology\n\n{self._methodology_summary()}\n\n"
            f"## Runtime\n\n"
            f"- Strategy: {self.strategy.describe()}\n"
            f"- Resume requested: {self.resume}\n"
            f"- Max iterations: {self.config.execution.max_iterations}\n"
            f"- Lightweight mode: {self._is_lightweight_mode()}\n"
            f"- Target dimensions total: {self.config.scoring.target_dimensions_total}\n"
            f"- Allowed tools: {self.config.execution.allowed_tools or '(none)'}\n"
        )
        with self._audit_trail.step("write_methods", artifact_root=self.output_dir):
            self.methods_path.write_text(content, encoding="utf-8")

    def _print_summary(self) -> None:
        """Print a session summary to stdout."""
        print("\n" + "=" * 60)
        print("  AUTORESEARCH SESSION COMPLETE")
        print("=" * 60)
        print(f"  Strategy:    {self.strategy.describe()}")
        print(f"  Topic:       {self.config.topic}")
        print()
        print(f"  Iterations:  {self.iteration}")
        print(f"  Best score:  {self.best_score:.1f}")
        print(f"  Total cost:  ${self.total_cost:.3f}")
        print(f"  Tokens:      {self.total_input_tokens:,} in / {self.total_output_tokens:,} out")
        if self.per_backend_costs or self.per_backend_tokens:
            all_names = sorted(set(self.per_backend_costs) | set(self.per_backend_tokens))
            for name in all_names:
                cost = self.per_backend_costs.get(name, 0.0)
                tok = self.per_backend_tokens.get(name, {"input": 0, "output": 0})
                print(f"    {name}: {tok['input']:,} in / {tok['output']:,} out (${cost:.3f})")
        print(f"  Dimensions:  {len(self.explored_dimensions)} explored")
        self._print_rubric_summary()
        self._print_agreement_summary()
        print(f"  Results:     {self.results_path}")
        if self.synthesis_path.exists():
            print(f"  Synthesis:   {self.synthesis_path}")
        print("=" * 60)

    def _print_rubric_summary(self) -> None:
        """Print rubric grade in the completion banner if available."""
        from .artifacts import load_json_if_exists

        rubric = load_json_if_exists(self.rubric_path, {})
        if not rubric:
            return
        grade = rubric.get("grade", "?")
        score = rubric.get("overall_score", 0.0)
        dims = rubric.get("dimensions", {})
        print()
        print(f"  Rubric:      {grade} ({score:.2f})")
        print(f"    evidence_quality:      {dims.get('evidence_quality', 0):.2f}")
        print(f"    citation_coverage:     {dims.get('citation_coverage', 0):.2f}")
        print(f"    source_diversity:      {dims.get('source_diversity', 0):.2f}")
        print(f"    uncertainty_reporting: {dims.get('uncertainty_reporting', 0):.2f}")
        print(f"    actionability:         {dims.get('actionability', 0):.2f}")
        print(f"    contradiction_handling:{dims.get('contradiction_handling', 0):.2f}")
        print()

    def _print_agreement_summary(self) -> None:
        """Print inter-rater agreement in the completion banner if available."""
        from .artifacts import load_json_if_exists

        agreement = load_json_if_exists(self.output_dir / "agreement.json", {})
        if not agreement or agreement.get("dimensions_with_multiple_candidates", 0) == 0:
            return
        n = agreement["dimensions_with_multiple_candidates"]
        rate = agreement.get("decision_agreement_rate")
        kappa = agreement.get("cohens_kappa")
        delta = agreement.get("mean_score_delta")
        parts = [f"{n} dimensions"]
        if rate is not None:
            parts.append(f"{rate:.0%} decision agreement")
        if kappa is not None:
            parts.append(f"kappa {kappa:.2f}")
        print(f"  Agreement:   {', '.join(parts)}")
        if delta is not None:
            print(f"    mean score delta: {delta:.1f}")
        print()

    def _record_prompt_snapshot(self, backend: Backend, prompt: str, opts: CallOptions) -> None:
        """Capture each top-level backend prompt for reproducibility artifacts."""
        if not isinstance(prompt, str):
            return
        self._prompt_snapshots.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "iteration": self.iteration,
                "backend": backend.name,
                "model": opts.model,
                "max_turns": opts.max_turns,
                "stream": opts.stream,
                "has_function_tools": bool(opts.tools),
                "allowed_tools": opts.allowed_tools,
                "prompt": prompt,
            }
        )

    def _finalize_run_artifacts(self) -> None:
        """Write final manifest and metrics artifacts."""
        with self._audit_trail.step("finalize_run_artifacts", artifact_root=self.output_dir):
            finalize_run_artifacts(self)

    def _write_prompt_snapshot_artifact(self) -> None:
        """Write captured prompt inputs for later audit and replay."""
        self.prompt_snapshot_path = self.output_dir / "prompt_snapshot.json"
        write_prompt_snapshot(self.prompt_snapshot_path, prompts=self._prompt_snapshots)

    def _write_rerun_artifact(self) -> None:
        """Write a convenience shell script that replays the run."""
        self.rerun_script_path = self.output_dir / "rerun.sh"
        write_rerun_script(self.rerun_script_path, config_path=self.config_path, output_dir=self.output_dir)

    def _write_agreement_artifact(self) -> None:
        """Compute and write inter-rater agreement when multi-candidate data exists."""
        write_agreement_artifact(self)

    def _write_run_manifest(self) -> None:
        """Write a machine-readable manifest for reproducibility."""
        payload = run_manifest_payload(
            config=self.config,
            strategy_description=self.strategy.describe(),
            backends=self.backends,
            output_dir=self.output_dir,
            resume=self.resume,
            config_path=self.config_path,
            run_status=self._run_status,
            run_started_at=self._run_started_at,
            run_completed_at=self._run_completed_at,
            package_version=package_version(),
            git_commit=git_commit(),
            cli_version_resolver=cli_version,
        )
        self.manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_effective_config(self) -> None:
        """Write the normalized effective config snapshot for this run."""
        write_effective_config(self.paths.effective_config, config=self.config)

    # -- Security enforcement --------------------------------------------

    def _check_execution_policy(self, opts: CallOptions) -> None:
        """Raise :exc:`~src.policy_denial.PolicyDeniedError` if *opts* violates the active security policy.

        This gate runs after :func:`~src.backend_options.apply_backend_capabilities`
        so that ``allowed_tools`` reflects what the backend would actually use.

        Policy enforcement is **capability-based**: each tool in ``allowed_tools`` is
        looked up in the :data:`~src.tool_capabilities._TOOL_CAPABILITIES` registry.

        Enforcement order (first matching check raises):

        1. **Bash** (``allow_host_bash``): any tool classified with ``uses_host_shell=True``
           is denied when ``allow_host_bash=False``.
        2. **Network** (``sandbox.network_access``): when ``sandbox_active`` is ``True``,
           tools with a declared network destination type are validated via
           :meth:`guard_network_action`.
        3. **Unclassified** (``allowed_tools``): when ``sandbox_active`` is ``True``,
           any tool *not in the capability registry* is denied with
           ``reason_code="tool_unclassified"`` — the conservative-deny contract.
           In direct mode (``sandbox_active=False``) unclassified tools pass through.
        """
        sandbox = self._sandbox or self._make_transient_sandbox()
        policy = sandbox.policy
        tool_names = [t.strip() for t in (opts.allowed_tools or "").split(",") if t.strip()]
        classified = classify_allowed_tools(tool_names)

        # Bash check: any tool with uses_host_shell capability is denied when
        # allow_host_bash=False. Runs before network/unclassified checks.
        if not policy.is_host_bash_allowed():
            shell_tools = [name for name, caps in classified if caps and caps.uses_host_shell]
            if shell_tools:
                err = PolicyDeniedError(
                    reason_code="host_bash_disabled",
                    policy_field="allow_host_bash",
                    requested_action="execute_bash",
                )
                self._audit_trail.emit("policy_denied", **err.audit_payload())
                raise err

        # Network checks: only fire when sandboxing is operationally active.
        if policy.sandbox_active:
            web_tools = sorted(
                name for name, caps in classified
                if caps and caps.uses_network and caps.destination_type == "web"
            )
            if web_tools:
                self.guard_network_action(f"tool_dispatch:{web_tools[0]}", "web")

            other_tools = sorted(
                name for name, caps in classified
                if caps and caps.uses_network and caps.destination_type == "other"
            )
            if other_tools:
                self.guard_network_action(f"tool_dispatch:{other_tools[0]}", "other")

        # Unclassified check: when sandbox is active, deny any tool not in the registry.
        # Conservative-deny contract — unknown tools must be explicitly classified to run
        # under sandboxing.  Direct mode (sandbox_active=False) is not affected.
        if policy.sandbox_active:
            unclassified = sorted(name for name, caps in classified if caps is None)
            if unclassified:
                err = PolicyDeniedError(
                    reason_code="tool_unclassified",
                    policy_field="allowed_tools",
                    requested_action=f"tool_dispatch:{unclassified[0]}",
                )
                self._audit_trail.emit("policy_denied", **err.audit_payload())
                raise err

        # Write-intent: when sandbox is active, surface write-capable tools explicitly
        # in the audit trail.  Actual write-boundary enforcement happens later in
        # guard_path_write() at the point of the real write operation.
        if policy.sandbox_active:
            write_tools = sorted(
                name for name, caps in classified if caps and caps.may_write
            )
            if write_tools:
                self._audit_trail.emit("dispatch_write_intent", tools=write_tools)

    def guard_network_action(self, action: str, destination_type: str) -> None:
        """Raise :exc:`~src.policy_denial.PolicyDeniedError` if a networked action violates policy.

        This is **dispatch-level enforcement only** — not OS-level firewalling.
        Enforcement is active only when :attr:`sandbox_active` is ``True`` on
        the resolved policy (i.e. ``tool_execution_mode: sandboxed`` and
        ``sandbox.mode: tool_calls``).  Direct-mode runs are not affected.

        Parameters
        ----------
        action:
            Short label for the requested network action (used in denial messages
            and audit events).
        destination_type:
            ``"web"`` for HTTP/HTTPS destinations, ``"other"`` for anything else.
        """
        sandbox = self._sandbox or self._make_transient_sandbox()
        if not sandbox.policy.sandbox_active:
            return
        try:
            sandbox.validate_tool_request(action=action, destination_type=destination_type)
        except PolicyDeniedError as err:
            self._audit_trail.emit("policy_denied", **err.audit_payload())
            raise

    def guard_path_write(self, path: Path) -> None:
        """Raise :exc:`~src.policy_denial.PolicyDeniedError` if writing to *path* violates policy.

        This is an explicit gate intended for agent-requested write operations.
        Framework-internal writes (e.g. manifest, effective_config) are not
        routed through this guard — they always target ``output_dir`` which is
        within the allowed boundary by construction.

        Callers should invoke this before any write that originates from an
        agent tool invocation or any untrusted source.

        Delegates to :attr:`_sandbox` when available; constructs a transient
        executor for callers that run before setup (e.g. tests).
        """
        sandbox = self._sandbox or self._make_transient_sandbox()
        try:
            sandbox.validate_tool_request(action="write", write_path=path)
        except PolicyDeniedError as err:
            self._audit_trail.emit("policy_denied", **err.audit_payload())
            raise

    def _make_transient_sandbox(self) -> SandboxExecutor:
        """Return a one-off executor for callers that run before ``_setup_run``.

        Side-effect free: no workspace is prepared here.  The caller is
        responsible for calling :meth:`~SandboxExecutor.prepare_workspace`
        with the appropriate iteration argument.
        """
        policy = resolve_runtime_security_policy(self.config.security, self.paths)
        backend = select_sandbox_backend(self.config.security.sandbox, self.output_dir)
        return SandboxExecutor(policy, policy.workspace_dir, backend=backend)

    def _write_metrics(self) -> None:
        """Write machine-readable run metrics."""
        payload = metrics_payload(
            benchmark_id=self.config.evaluation.benchmark_id,
            run_status=self._run_status,
            iteration=self.iteration,
            best_score=self.best_score,
            explored_dimensions=self.explored_dimensions,
            discovered_dimensions=self.discovered_dimensions,
            total_cost=self.total_cost,
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            per_backend_costs=self.per_backend_costs,
            per_backend_tokens=self.per_backend_tokens,
            results=self.results,
            retry_summary=self._retry_summary,
            tool_loop_summary=self._tool_loop_summary,
        )
        self.metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_run_metadata_artifacts(self) -> None:
        """Write manifest and metrics artifacts through the shared helper."""
        write_run_metadata_artifacts(self)

    def _collect_provenance(self, text: str, *, scope: str, dimension: str = "") -> None:
        """Collect claims and citations from generated content."""
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for claim in extract_claims(text, scope=scope, dimension=dimension):
            claim["id"] = f"{scope}-{claim['id']}"
            self._claims.append(claim)
        for citation in extract_citations(text, scope=scope, retrieved_at=retrieved_at):
            citation["id"] = f"{scope}-{citation['id']}"
            self._citations.append(citation)

    def _write_provenance_artifacts(self) -> None:
        """Write claim and citation artifacts."""
        benchmark_summary = self._benchmark_summary()
        reference_comparison = self._reference_run_comparison()
        bundle = build_provenance_bundle(
            claims=self._claims,
            citations=self._citations,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
        )
        evidence_links = bundle["evidence_links"]
        search_log = bundle["search_log"]
        screening_log = bundle["screening_log"]
        evidence_quality = bundle["evidence_quality"]
        contradictions = bundle["contradictions"]
        rubric = bundle["rubric"]
        semantic_review = self._semantic_review(
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            contradictions=contradictions,
        )
        semantic_calibration = self._semantic_calibration(
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
        )
        write_provenance_artifacts_bundle(
            self.paths,
            claims=self._claims,
            citations=self._citations,
            bundle=bundle,
            semantic_review=semantic_review,
            semantic_calibration=semantic_calibration,
        )
        self._write_evaluation_artifact(
            evidence_quality,
            rubric,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
            semantic_review=semantic_review,
            semantic_calibration=semantic_calibration,
        )

    def _generate_baseline(self) -> None:
        """Generate an optional single-pass baseline answer for comparison."""
        if not self.config.evaluation.run_baselines:
            return
        prompt = _render(
            "research_baseline.md",
            topic=self.config.topic,
            goal=self.config.goal,
            methodology=self._methodology_summary(),
            goal_constraints=self._goal_constraints_summary(),
            lightweight_mode="yes" if self._is_lightweight_mode() else "no",
        )
        baseline_backend = self.strategy.get_synthesize_backend()
        with self._audit_trail.step(
            "generate_baseline",
            artifact_root=self.output_dir,
            iteration=self.iteration,
            backend=baseline_backend.name,
        ):
            resp = self._call_with(baseline_backend, prompt, max_turns=3)
            self._track_usage(resp, baseline_backend.name)
        if not resp.is_error and resp.text:
            final_text = self._postprocess_goal_output(resp.text)
            self.baseline_path.write_text(final_text, encoding="utf-8")
            self._collect_provenance(final_text, scope="baseline")

    def _write_evaluation_artifact(
        self,
        evidence_quality: dict[str, Any],
        rubric: dict[str, Any],
        *,
        benchmark_summary: dict[str, Any],
        reference_comparison: dict[str, Any],
        semantic_review: dict[str, Any],
        semantic_calibration: dict[str, Any],
    ) -> None:
        """Write optional evaluation summary comparing iterative output to a baseline."""
        write_evaluation_artifacts(
            self,
            evidence_quality=evidence_quality,
            rubric=rubric,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
            semantic_review=semantic_review,
            semantic_calibration=semantic_calibration,
        )

    def _write_html_report(self) -> None:
        write_html_report(self.output_dir, config=self.config, render_fn=render_html_report_fn)

    def _write_pdf_report(self) -> None:
        write_pdf_report(
            self.output_dir,
            config=self.config,
            best_score=self.best_score,
            iteration=self.iteration,
            explored_dimensions=self.explored_dimensions,
            render_pdf_fn=render_simple_pdf,
        )

    def _write_dashboard_artifact(self) -> None:
        write_dashboard(
            self.output_dir,
            config=self.config,
            best_score=self.best_score,
            iteration=self.iteration,
            explored_dimensions=self.explored_dimensions,
            retry_summary=self._retry_summary,
            tool_loop_summary=self._tool_loop_summary,
            latest_score_breakdown=self._latest_score_breakdown_payload(),
        )

    def _latest_score_breakdown_payload(self) -> dict[str, Any] | None:
        """Build the dashboard payload for the most recent iteration's
        score components.  Returns ``None`` when no iteration has scored
        yet (e.g. cold-start dashboard, synthesise-only mode without
        loaded prior state).
        """
        score = getattr(self, "_latest_score", None)
        if score is None:
            return None
        breakdown = score.heuristic_breakdown
        return {
            "iteration": self.iteration,
            "coverage": score.coverage,
            "quality": score.quality,
            "total": score.total,
            "components": {
                "dimension_points": breakdown.dimension_points,
                "evidence_points": breakdown.evidence_points,
                "new_questions_points": breakdown.new_questions_points,
                "length_points": breakdown.length_points,
                "target_dimension": breakdown.target_dimension,
            },
            "judge_axes": {
                "depth": score.judge_depth,
                "accuracy": score.judge_accuracy,
                "novelty": score.judge_novelty,
                "actionability": score.judge_actionability,
            },
        }

    def _write_tool_trace_artifact(self) -> None:
        from .artifacts import tool_trace_payload

        payload = tool_trace_payload(tool_trace=self._tool_trace)
        self.tool_trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.tool_trace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_portfolio_artifacts(self) -> None:
        write_portfolio(self.output_dir, build_portfolio, render_portfolio_html)

    def _write_reporting_artifacts(self) -> None:
        """Write dashboard, trace, report, and portfolio artifacts."""
        write_reporting_artifacts(self)

    def _semantic_review(
        self,
        *,
        rubric: dict[str, Any],
        evidence_quality: dict[str, Any],
        benchmark_summary: dict[str, Any],
        contradictions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Optionally run a final judge pass over the synthesized report."""
        if not self.config.evaluation.semantic_review:
            return semantic_review_disabled()

        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        judge_backend = self.strategy.get_judge_backend()
        if not synthesis_text.strip():
            return semantic_review_empty(judge_backend=judge_backend.name)

        prompt = _render(
            "research_semantic_judge.md",
            topic=self.config.topic,
            methodology=self._methodology_summary(),
            synthesis=synthesis_text,
            rubric=json.dumps(rubric, indent=2),
            evidence_quality=json.dumps(evidence_quality, indent=2),
            benchmark_summary=json.dumps(benchmark_summary, indent=2),
            contradictions=json.dumps(contradictions, indent=2),
        )
        resp = self._call_with(judge_backend, prompt, max_turns=3)
        self._track_usage(resp, judge_backend.name)

        fallback = semantic_review_fallback(
            judge_backend=judge_backend.name,
            rubric=rubric,
            evidence_quality=evidence_quality,
            raw_response=resp.text,
        )

        if resp.is_error or not resp.text:
            return fallback
        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError:
            return fallback

        return semantic_review_from_payload(payload, judge_backend=judge_backend.name, raw_response=resp.text)

    def _semantic_calibration(
        self,
        *,
        rubric: dict[str, Any],
        evidence_quality: dict[str, Any],
        benchmark_summary: dict[str, Any],
        reference_comparison: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine rubric, benchmark, evidence, and consistency into a calibrated quality score."""
        return semantic_calibration(
            enabled=self.config.evaluation.semantic_calibration,
            goal=self.config.goal,
            methodology_question=self.config.methodology.question,
            methodology_scope=self.config.methodology.scope,
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark_summary,
            reference_comparison=reference_comparison,
        )

    def _reference_run_comparison(self) -> dict[str, Any]:
        """Compare the current run to referenced prior outputs for consistency analysis."""
        return reference_run_comparison(
            reference_runs=self.config.evaluation.reference_runs,
            current_strategy=self.config.execution.strategy,
            current_best_score=self.best_score,
            current_dimensions=self.explored_dimensions,
            claims=self._claims,
            citations=self._citations,
        )

    def _benchmark_summary(self) -> dict[str, Any]:
        """Evaluate current run outputs against optional benchmark expectations."""
        synthesis_text = self.synthesis_path.read_text(encoding="utf-8") if self.synthesis_path.exists() else ""
        return benchmark_summary(
            benchmark_id=self.config.evaluation.benchmark_id,
            config_expected_dimensions=list(self.config.evaluation.expected_dimensions),
            config_required_keywords=list(self.config.evaluation.required_keywords),
            knowledge_text=self.knowledge_base or "",
            synthesis_text=synthesis_text,
        )
