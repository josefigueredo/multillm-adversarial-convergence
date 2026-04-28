"""Implement loop — state types and context for the adversarial code-task loop.

MM09: Safe Adversarial Implement Mode.

Key design decisions
--------------------
- :class:`ImplementTarget` captures the **target repo contract**: the repo to
  modify, the execution level, and the allowed write roots.  It is *frozen*
  so callers cannot widen the safety boundary after construction.
- ``execution_level`` defaults to ``"patch_only"`` — the safest option that
  never directly mutates any repository.
- :class:`CandidatePatch` is the central artifact: every strategy phase
  receives and/or produces one.
- :class:`TaskState` tracks mutable loop state; ``current_workflow_state`` uses
  :class:`~src.workflows.implement_states.ImplementState` for audit-trail
  compatibility.
- HITL/deferred semantics are out of scope for Step 3; they are addressed in a
  future step.  The convergence criterion is: no valid critiques in the current
  cycle (``status == "valid"``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.config import (
    BackendsConfig,
    ProviderConfig,
    _parse_backends_config,
    _parse_providers_config,
    _validate_provider_references,
)
from src.run_state import BaseContext
from src.workflows.implement_states import ImplementState
from src.workflows.transitions import WorkflowTransitionEmitter

log = logging.getLogger("autoresearch")


#: Execution levels available for implement mode.
#:
#: ``analyze_only``   — no writes; planning and critique only.
#: ``patch_only``     — generate a diff/patch; no direct mutation of any repo.
#: ``isolated_apply`` — apply in a temporary worktree/clone; never the live repo.
VALID_EXECUTION_LEVELS: tuple[str, ...] = (
    "analyze_only",
    "patch_only",
    "isolated_apply",
)


# ---------------------------------------------------------------------------
# Target repo contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImplementTarget:
    """Explicit contract describing the target repository and safety boundaries.

    This is the *first* thing an implement run establishes — it separates the
    planner/orchestrator repo from the repo being modified.

    Attributes
    ----------
    path:
        Filesystem path of the target repository root.
    execution_level:
        One of :data:`VALID_EXECUTION_LEVELS`.  Defaults to ``"patch_only"``
        (safe default — no direct mutation).
    allowed_roots:
        Tuple of relative paths (relative to *path*) where writes are permitted.
        Empty tuple means "no paths explicitly allowed" — enforcement is a
        Step-4 concern.
    """

    path: Path
    execution_level: str = "patch_only"
    allowed_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if self.execution_level not in VALID_EXECUTION_LEVELS:
            raise ValueError(
                f"Invalid execution_level '{self.execution_level}'. "
                f"Must be one of: {', '.join(VALID_EXECUTION_LEVELS)}"
            )
        for root in self.allowed_roots:
            root_path = root if isinstance(root, Path) else Path(root)
            if root_path.is_absolute():
                raise ValueError(
                    f"allowed_roots must be relative paths (not absolute): {root}"
                )
            if ".." in root_path.parts:
                raise ValueError(
                    f"allowed_roots must not contain parent traversal: {root}"
                )


# ---------------------------------------------------------------------------
# Implement config (loaded from YAML)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImplementConfig:
    """Top-level configuration for an implement run.

    Attributes
    ----------
    target:
        Explicit target-repo contract: path, execution level, allowed roots.
    task_description:
        Natural-language description of what to implement.
    max_cycles:
        Maximum adversarial cycles.  ``0`` means unlimited.
    convergence_cycles:
        Consecutive clean cycles required to declare convergence.
    allow_same_repo:
        When ``True``, allows the target path to be the same repository as
        this planner/orchestrator.  Defaults to ``False`` (safe) — same-repo
        self-hosting is a high-risk operation and requires explicit opt-in.
    """

    target: ImplementTarget
    task_description: str = ""
    max_cycles: int = 5
    convergence_cycles: int = 1
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    allow_same_repo: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "ImplementConfig":
        """Load and validate an implement config from a YAML file.

        Parameters
        ----------
        path:
            Path to the config YAML file.

        Raises
        ------
        OSError
            If the file cannot be read.
        ValueError
            If the YAML is malformed or the config contract is not satisfied.
        """
        import yaml  # lazy import — matches project convention

        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in implement config: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(
                "Implement config must be a YAML mapping at the top level"
            )

        target_data = raw.get("target")
        if not isinstance(target_data, dict):
            raise ValueError(
                "Implement config must have a 'target' mapping "
                "(e.g.  target:\\n  path: /path/to/repo)"
            )

        target_path_str = target_data.get("path")
        if not target_path_str or not isinstance(target_path_str, str):
            raise ValueError(
                "Implement config must specify target.path as a non-empty string"
            )

        # Resolve relative paths against the config file's own directory so
        # behaviour is not CWD-dependent.
        target_path = Path(target_path_str)
        if not target_path.is_absolute():
            target_path = (path.parent / target_path).resolve()

        if not target_path.exists():
            raise ValueError(
                f"Implement target path does not exist: {target_path}"
            )
        if not target_path.is_dir():
            raise ValueError(
                f"Implement target path must be a directory, not a file: {target_path}"
            )

        execution_level = target_data.get("execution_level", "patch_only")
        if not isinstance(execution_level, str):
            raise ValueError(
                f"target.execution_level must be a string, got "
                f"{type(execution_level).__name__!r}"
            )

        allowed_roots_raw = target_data.get("allowed_roots", [])
        if not isinstance(allowed_roots_raw, (list, tuple)):
            raise ValueError(
                "target.allowed_roots must be a list of relative path strings"
            )
        if not all(isinstance(r, str) for r in allowed_roots_raw):
            raise ValueError(
                "target.allowed_roots entries must all be strings"
            )
        allowed_roots = tuple(Path(r) for r in allowed_roots_raw)

        # Self-hosting safety gate — detect if target_path contains this very repo.
        # If the orchestrator source file is reachable relative to target_path, then
        # target_path is an ancestor (or equal to) the planner repo root, which is
        # self-hosting.  This is disabled by default; opt-in via allow_same_repo: true.
        allow_same_repo = bool(raw.get("allow_same_repo", False))
        _orchestrator_file = Path(__file__).resolve()
        try:
            _orchestrator_file.relative_to(target_path.resolve())
            _is_same_repo = True
        except ValueError:
            _is_same_repo = False

        if _is_same_repo and not allow_same_repo:
            raise ValueError(
                f"Implement target '{target_path}' contains this planner repository. "
                "Self-hosting is a high-risk operation and is disabled by default. "
                "Set 'allow_same_repo: true' in your implement config to explicitly opt in."
            )

        # Top-level cycle configuration
        convergence_cycles = int(raw.get("convergence_cycles", 1))
        if convergence_cycles < 1:
            raise ValueError(
                f"convergence_cycles must be >= 1, got {convergence_cycles}"
            )
        max_cycles = int(raw.get("max_cycles", 5))
        task_description = str(raw.get("task_description", "") or "")

        # Backend / provider config — mirrors DocumentConfig / PlanConfig exactly:
        # when providers are declared, build BackendsConfig from provider instance
        # names directly (never route through _parse_backends_config which validates
        # against VALID_BACKENDS adapter names, not instance names).
        providers = _parse_providers_config(raw.get("providers", {}))
        if providers:
            backends_raw = raw.get("backends", {})
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
        else:
            backends_config = _parse_backends_config(raw.get("backends", {}))

        return cls(
            target=ImplementTarget(
                path=target_path,
                execution_level=execution_level,
                allowed_roots=allowed_roots,
            ),
            task_description=task_description,
            max_cycles=max_cycles,
            convergence_cycles=convergence_cycles,
            backends=backends_config,
            providers=providers,
            allow_same_repo=allow_same_repo,
        )


# ---------------------------------------------------------------------------
# Task and patch artifacts
# ---------------------------------------------------------------------------

@dataclass
class ImplementTask:
    """A single code implementation task.

    Attributes
    ----------
    description:
        Natural-language description of what needs to be implemented.
    target_file_refs:
        Optional hints about which files the task involves.
    """

    description: str
    target_file_refs: tuple[str, ...] = ()


@dataclass
class CandidatePatch:
    """A code patch generated or revised by a strategy phase.

    The ``content`` field holds the patch text (unified diff, file content,
    or any format agreed upon by the builder/arbitrator prompts).  All strategy
    phases operate on :class:`CandidatePatch` rather than raw strings to keep
    the contract explicit.

    Attributes
    ----------
    content:
        The patch/diff text.
    rationale:
        Builder or arbitrator explanation of the change.
    touched_files:
        Files affected by this patch.
    """

    content: str
    rationale: str = ""
    touched_files: tuple[str, ...] = ()


@dataclass
class ImplementCritique:
    """Raw critique from the Challenger about a candidate patch.

    Attributes
    ----------
    description:
        Natural-language description of the problem.
    file_ref:
        File or area of the patch being critiqued.
    raised_by:
        Role that raised this critique (e.g. ``"challenger"``).
    """

    description: str
    file_ref: str
    raised_by: str


@dataclass
class VerifiedImplementCritique:
    """A critique classified by the Verifier.

    Attributes
    ----------
    description:
        Original critique description.
    file_ref:
        File or area being critiqued.
    raised_by:
        Role that raised this critique.
    status:
        ``"valid"`` — must be addressed in the revised patch.
        ``"stale"`` — no longer applicable to the current patch.
        Note: ``"deferred"``/HITL semantics are out of scope for Step 3.
    """

    description: str
    file_ref: str
    raised_by: str
    status: str  # "valid" | "stale"


# ---------------------------------------------------------------------------
# Loop state
# ---------------------------------------------------------------------------

@dataclass
class TaskState:
    """Mutable state for the implement convergence loop.

    Attributes
    ----------
    task:
        The implementation task being worked on.
    cycle:
        Current loop cycle number (0-indexed; incremented at start of each cycle).
    converged:
        ``True`` only when the stopping criterion was clean-cycle convergence,
        not when the loop stopped due to ``max_cycles``.
    patches:
        Full history of :class:`CandidatePatch` objects produced (builder +
        arbitrator outputs).
    critiques:
        Full history of :class:`VerifiedImplementCritique` across all cycles
        (the "critique bundle" artifact).
    pending_critiques:
        Valid critiques from the *most recent* cycle, passed to the builder
        on the next cycle so it can incorporate accepted feedback.  Cleared
        after each builder invocation.
    consecutive_clean_cycles:
        Number of consecutive cycles with zero valid critiques.
    current_workflow_state:
        Current :class:`~src.workflows.implement_states.ImplementState`.
    """

    task: ImplementTask
    cycle: int = 0
    converged: bool = False
    patches: list[CandidatePatch] = field(default_factory=list)
    critiques: list[VerifiedImplementCritique] = field(default_factory=list)
    pending_critiques: list[VerifiedImplementCritique] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    current_workflow_state: ImplementState = ImplementState.IDLE
    boundary_violations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cycle context
# ---------------------------------------------------------------------------

@dataclass
class ImplementCycleContext(BaseContext):
    """Callback bundle for the implement loop.

    Extends :class:`~src.run_state.BaseContext` (call_with,
    invoke_for_strategy, track_usage, track_cost) with implement-specific
    fields.
    """

    target: ImplementTarget
    audit_trail: Any


# ---------------------------------------------------------------------------
# Cycle execution
# ---------------------------------------------------------------------------

def run_implement_cycle(
    state: TaskState,
    ctx: ImplementCycleContext,
    strategy: Any,
) -> tuple[int, int, int]:
    """Execute one adversarial implement cycle.

    Phases: Builder → Challenger → Verifier → (Arbitrator if valid critiques).

    Returns
    -------
    tuple[int, int, int]
        ``(valid_count, stale_count, deferred_count)``.
    """
    state.cycle += 1
    log.info("[implement][cycle %03d] starting", state.cycle)

    emitter = WorkflowTransitionEmitter(
        ctx.audit_trail, "implement", state.current_workflow_state
    )

    # 1. Builder — generate patch (cycle 1) or improve from previous patch +
    #    accepted critiques (cycle N+1).
    last_patch = state.patches[-1] if state.patches else None
    accepted = list(state.pending_critiques)
    emitter.transition(ImplementState.BUILDER, cycle=state.cycle)
    log.info("[implement][cycle %03d] builder starting", state.cycle)
    patch = strategy.run_builder(
        state.task,
        ctx.target,
        last_patch=last_patch,
        accepted_critiques=accepted,
        invoke=ctx.call_with,
    )
    state.patches.append(patch)
    state.pending_critiques = []  # consumed

    # 1b. Boundary safety check — before any further phases, verify the patch
    #     does not touch files outside allowed_roots.  If violated, record and
    #     abort the cycle immediately (challenger/verifier/arbitrator skipped).
    violations = validate_patch_boundaries(patch, ctx.target)
    if violations:
        state.boundary_violations.extend(violations)
        log.error(
            "[implement][cycle %03d] BOUNDARY VIOLATION — stopping loop: %s",
            state.cycle, "; ".join(violations),
        )
        state.current_workflow_state = emitter.current_state
        return 0, 0, 0

    # 2. Challenger
    emitter.transition(ImplementState.CHALLENGER, cycle=state.cycle)
    log.info("[implement][cycle %03d] challenger starting", state.cycle)
    raw_critiques = strategy.run_challenger(
        patch, state.task, ctx.target, invoke=ctx.call_with
    )

    # 3. Verifier
    emitter.transition(ImplementState.VERIFIER, cycle=state.cycle)
    log.info("[implement][cycle %03d] verifier starting (%d critique(s))", state.cycle, len(raw_critiques))
    verified = strategy.run_verifier(
        patch, raw_critiques, state.task, ctx.target, invoke=ctx.call_with
    )

    # 4. Classify
    valid = [v for v in verified if v.status == "valid"]
    stale = [v for v in verified if v.status == "stale"]
    deferred = [v for v in verified if v.status not in ("valid", "stale")]

    # 5. Arbitrator — only when there are valid critiques to address
    emitter.transition(ImplementState.ARBITRATOR, cycle=state.cycle)
    if valid:
        log.info("[implement][cycle %03d] arbitrator starting (%d valid critique(s))", state.cycle, len(valid))
        revised = strategy.run_arbitrator(
            patch, valid, state.task, ctx.target, invoke=ctx.call_with
        )
        # 5b. Boundary check on the revised patch — the arbitrator is a
        #     patch-producing phase and must satisfy the same boundary contract.
        arb_violations = validate_patch_boundaries(revised, ctx.target)
        if arb_violations:
            state.boundary_violations.extend(arb_violations)
            log.error(
                "[implement][cycle %03d] BOUNDARY VIOLATION in arbitrator patch — stopping loop: %s",
                state.cycle, "; ".join(arb_violations),
            )
            # Do NOT carry the out-of-bounds revised patch forward.
            state.current_workflow_state = emitter.current_state
            return 0, 0, 0
        state.patches.append(revised)
        state.pending_critiques = list(valid)  # carry forward for next builder
    else:
        log.info("[implement][cycle %03d] arbitrator skipped (no valid critiques)", state.cycle)

    # 6. Accumulate full critique history
    state.critiques.extend(verified)

    # 7. Update convergence counter
    if not valid:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0

    state.current_workflow_state = emitter.current_state
    log.info(
        "[implement][cycle %03d] done (valid=%d stale=%d deferred=%d clean_streak=%d)",
        state.cycle, len(valid), len(stale), len(deferred),
        state.consecutive_clean_cycles,
    )
    return len(valid), len(stale), len(deferred)


# ---------------------------------------------------------------------------
# Convergence helpers
# ---------------------------------------------------------------------------

def _should_stop_implement(state: TaskState, config: ImplementConfig) -> bool:
    """Return ``True`` when the implement loop should terminate."""
    if state.boundary_violations:
        return True
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles


# ---------------------------------------------------------------------------
# Patch boundary validation
# ---------------------------------------------------------------------------

def validate_patch_boundaries(
    patch: "CandidatePatch", target: "ImplementTarget"
) -> list[str]:
    """Return boundary violation descriptions for files outside *allowed_roots*.

    Parameters
    ----------
    patch:
        The patch produced by the builder or arbitrator.
    target:
        The implement target contract providing ``allowed_roots``.

    Returns
    -------
    list[str]
        Empty list when the patch is within bounds.  Each entry describes one
        violation (file path + reason).  A non-empty list means the patch
        must NOT proceed to apply.

    Notes
    -----
    When ``target.allowed_roots`` is empty, no boundaries are declared and all
    files are considered in-scope (permissive default for configs that omit
    ``allowed_roots``).  Absolute paths in ``touched_files`` are always
    violations when ``allowed_roots`` is non-empty, because they cannot be
    safely compared with relative root constraints.
    """
    if not target.allowed_roots:
        return []

    violations: list[str] = []
    for file_str in patch.touched_files:
        p = Path(file_str)
        if p.is_absolute():
            violations.append(f"absolute path not permitted in touched_files: {file_str}")
            continue
        in_allowed = any(
            p == root or p.parts[: len(root.parts)] == root.parts
            for root in target.allowed_roots
        )
        if not in_allowed:
            roots_display = ", ".join(str(r) for r in target.allowed_roots)
            violations.append(
                f"file outside allowed_roots [{roots_display}]: {file_str}"
            )
    return violations
