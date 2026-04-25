"""Document convergence loop — state types, context, and cycle execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import logging

from .backends import AgentResponse
from .config import DocumentConfig
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .run_state import BaseContext
from .workflows.refine_states import RefineState
from .workflows.transitions import WorkflowTransitionEmitter


log = logging.getLogger("autoresearch")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """A critique raised by the Challenger or a persona, tracked across cycles."""

    id: str
    description: str
    raised_by: str          # "challenger" | persona name
    cycle: int
    section_ref: str
    status: str             # "open" | "valid" | "stale" | "deferred" | "resolved"
    defer_reason: str | None = None
    verified_cycle: int | None = None
    patch_applied: bool = False


@dataclass
class CycleState:
    """Mutable state for the document convergence loop."""

    prd: str = ""
    prd_path: Path = field(default_factory=lambda: Path("PRD.md"))
    prd_versions: list[str] = field(default_factory=list)
    cycle: int = 0
    issue_registry: list[Issue] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    pending_human_inputs: list[HumanInputRequest] = field(default_factory=list)
    human_decisions: list[HumanDecision] = field(default_factory=list)
    pending_patches: list[Any] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    results_path: Path = field(default_factory=lambda: Path("results.tsv"))
    current_workflow_state: RefineState = RefineState.IDLE


@dataclass
class CycleContext(BaseContext):
    """Callback bundle for the document loop.

    Extends ``BaseContext`` (call_with, invoke_for_strategy, track_usage,
    track_cost) with document-specific state.
    """

    config: DocumentConfig
    human_decisions: list[HumanDecision]
    read_prd_section: Callable[[str], str]
    update_issue_registry: Callable[[list[Any]], None]
    audit_trail: Any
    artifact_root: Path


# ---------------------------------------------------------------------------
# Convergence helpers
# ---------------------------------------------------------------------------

def _should_stop(state: CycleState, config: DocumentConfig) -> bool:
    """Return True when the run should terminate."""
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles


def _update_convergence(
    state: CycleState,
    valid_count: int,
    human_required_count: int,
) -> None:
    """Increment or reset the clean-cycle counter.

    A cycle is clean only when there are zero VALID critiques AND zero
    human_required deferrals. STALE and out_of_scope/needs_research
    deferrals do not reset the counter.
    """
    if valid_count == 0 and human_required_count == 0:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0


# ---------------------------------------------------------------------------
# Cycle execution
# ---------------------------------------------------------------------------

def run_cycle(
    state: CycleState,
    ctx: CycleContext,
    strategy: Any,
    *,
    interactive: bool = True,
) -> tuple[int, int, int]:
    """Execute one convergence cycle.

    Returns:
        Tuple of (valid_count, stale_count, deferred_count).
    """
    state.cycle += 1
    log.info("[refine][cycle %03d] starting convergence cycle", state.cycle)

    emitter = WorkflowTransitionEmitter(ctx.audit_trail, "refine", state.current_workflow_state)

    # 1. Builder — generate or apply pending patches
    log.info(
        "[refine][cycle %03d] builder starting (pending patches: %d, human decisions: %d)",
        state.cycle,
        len(state.pending_patches),
        len(ctx.human_decisions),
    )
    emitter.transition(RefineState.BUILDER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "builder",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="refine",
    ):
        prd = strategy.run_builder(
            state.prd,
            state.pending_patches,
            ctx.call_with,
            human_decisions=ctx.human_decisions,
        )
    state.prd = prd
    state.prd_versions.append(prd)
    state.pending_patches = []
    log.info("[refine][cycle %03d] builder completed", state.cycle)

    # 2. Challenger
    log.info("[refine][cycle %03d] challenger starting", state.cycle)
    emitter.transition(RefineState.CHALLENGER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "challenger",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="refine",
    ):
        raw_critiques = strategy.run_challenger(prd, ctx.call_with)
    log.info(
        "[refine][cycle %03d] challenger completed (%d critique(s))",
        state.cycle,
        len(raw_critiques),
    )

    # 3. Personas
    log.info(
        "[refine][cycle %03d] personas starting (%d persona(s), mode=%s)",
        state.cycle,
        len(ctx.config.personas),
        ctx.config.persona_mode,
    )
    emitter.transition(RefineState.PERSONAS, cycle=state.cycle)
    with ctx.audit_trail.step(
        "personas",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="refine",
    ):
        persona_critiques = strategy.run_personas(prd, ctx.call_with)
    log.info(
        "[refine][cycle %03d] personas completed (%d critique(s))",
        state.cycle,
        len(persona_critiques),
    )

    all_raw = raw_critiques + persona_critiques

    # 4. Verifier
    log.info(
        "[refine][cycle %03d] verifier starting (%d critique(s) to classify)",
        state.cycle,
        len(all_raw),
    )
    emitter.transition(RefineState.VERIFIER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "verifier",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="refine",
    ):
        verified = strategy.run_verifier(prd, all_raw, ctx.call_with)
    log.info(
        "[refine][cycle %03d] verifier completed (%d classified critique(s))",
        state.cycle,
        len(verified),
    )

    # 5. Classify
    valid = [v for v in verified if v.status == "valid"]
    stale = [v for v in verified if v.status == "stale"]
    deferred = [v for v in verified if v.status == "deferred"]
    human_required = [
        v for v in deferred if v.defer_reason == DeferReason.HUMAN_REQUIRED
    ]

    # 6. HITL gate
    if human_required:
        log.info(
            "[refine][cycle %03d] human input required for %d critique(s)",
            state.cycle,
            len(human_required),
        )
        requests = _make_human_requests(human_required, state.cycle, state.issue_registry)
        state.pending_human_inputs = requests
        emitter.transition(RefineState.PAUSED_FOR_HUMAN, cycle=state.cycle)
        if interactive:
            from .hitl import collect_interactive
            decisions = collect_interactive(requests)
            state.human_decisions.extend(decisions)
            ctx.human_decisions.extend(decisions)
            state.pending_human_inputs = []

    # 7. Arbitrator — patches for VALID only
    log.info(
        "[refine][cycle %03d] arbitrator starting (%d valid critique(s))",
        state.cycle,
        len(valid),
    )
    emitter.transition(RefineState.ARBITRATOR, cycle=state.cycle)
    with ctx.audit_trail.step(
        "arbitrator",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="refine",
    ):
        new_patches = strategy.run_arbitrator(prd, valid, ctx.call_with)
    state.pending_patches = new_patches
    log.info(
        "[refine][cycle %03d] arbitrator completed (%d patch(es))",
        state.cycle,
        len(new_patches),
    )

    # 8. Update issue registry
    _register_issues(state, verified)

    # 9. Update convergence counter
    _update_convergence(
        state,
        valid_count=len(valid),
        human_required_count=len(human_required),
    )
    log.info(
        "[refine][cycle %03d] cycle complete (valid=%d stale=%d deferred=%d clean_streak=%d)",
        state.cycle,
        len(valid),
        len(stale),
        len(deferred),
        state.consecutive_clean_cycles,
    )

    state.current_workflow_state = emitter.current_state
    return len(valid), len(stale), len(deferred)


def _make_human_requests(
    human_required: list[Any],
    cycle: int,
    issue_registry: list[Issue],
) -> list[HumanInputRequest]:
    """Build HumanInputRequest objects from human_required VerifiedCritiques."""
    next_id = len(issue_registry) + 1
    requests = []
    for i, v in enumerate(human_required):
        requests.append(HumanInputRequest(
            issue_id=f"I-{next_id + i:02d}",
            question=v.question or v.description,
            context=v.section_ref,
            suggested_answer=v.suggested_answer or "",
            cycle=cycle,
        ))
    return requests


def _register_issues(state: CycleState, verified: list[Any]) -> None:
    """Add newly verified critiques to the issue registry with sequential IDs."""
    next_id = len(state.issue_registry) + 1
    for i, v in enumerate(verified):
        issue = Issue(
            id=f"I-{next_id + i:02d}",
            description=v.description,
            raised_by=v.raised_by,
            cycle=state.cycle,
            section_ref=v.section_ref,
            status=v.status,
            defer_reason=v.defer_reason,
            verified_cycle=state.cycle,
        )
        state.issue_registry.append(issue)
