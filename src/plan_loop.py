"""Plan convergence loop — state types, context, and cycle execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import logging

from .config import PlanConfig
from .document_loop import (
    Issue,
    _make_human_requests,
    _register_issues,
)
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .run_state import BaseContext
from .workflows.plan_states import PlanState
from .workflows.transitions import WorkflowTransitionEmitter


log = logging.getLogger("autoresearch")


@dataclass
class PlanCycleState:
    """Mutable state for the plan convergence loop."""

    plan: str = ""
    plan_path: Path = field(default_factory=lambda: Path("PLAN.md"))
    plan_versions: list[str] = field(default_factory=list)
    cycle: int = 0
    issue_registry: list[Issue] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    pending_human_inputs: list[HumanInputRequest] = field(default_factory=list)
    human_decisions: list[HumanDecision] = field(default_factory=list)
    pending_patches: list[Any] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    current_workflow_state: PlanState = PlanState.IDLE


@dataclass
class PlanCycleContext(BaseContext):
    """Callback bundle for the plan loop.

    Extends ``BaseContext`` (call_with, invoke_for_strategy, track_usage,
    track_cost) with plan-specific state.
    """

    config: PlanConfig
    human_decisions: list[HumanDecision]
    update_issue_registry: Callable[[list[Any]], None]
    audit_trail: Any
    artifact_root: Path
    guidance_context: str = ""


def _plan_should_stop(state: PlanCycleState, config: PlanConfig) -> bool:
    """Return True when the plan convergence run should terminate."""
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles


def _update_plan_convergence(
    state: PlanCycleState,
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


def run_plan_cycle(
    state: PlanCycleState,
    ctx: PlanCycleContext,
    strategy: Any,
    *,
    interactive: bool = True,
) -> tuple[int, int, int]:
    """Execute one plan convergence cycle.

    Returns:
        Tuple of (valid_count, stale_count, deferred_count).
    """
    state.cycle += 1
    log.info("[plan][cycle %03d] starting convergence cycle", state.cycle)

    emitter = WorkflowTransitionEmitter(ctx.audit_trail, "plan", state.current_workflow_state)

    # 1. Builder — apply pending patches and produce revised plan
    log.info(
        "[plan][cycle %03d] builder starting (pending patches: %d, human decisions: %d)",
        state.cycle,
        len(state.pending_patches),
        len(ctx.human_decisions),
    )
    emitter.transition(PlanState.BUILDER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "builder",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="plan",
    ):
        plan = strategy.run_builder(
            state.plan,
            state.pending_patches,
            ctx.call_with,
            human_decisions=ctx.human_decisions,
            guidance_context=ctx.guidance_context,
        )
    state.plan = plan
    state.plan_versions.append(plan)
    state.pending_patches = []
    log.info("[plan][cycle %03d] builder completed", state.cycle)

    # 2. Challenger
    log.info("[plan][cycle %03d] challenger starting", state.cycle)
    emitter.transition(PlanState.CHALLENGER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "challenger",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="plan",
    ):
        raw_critiques = strategy.run_challenger(plan, ctx.call_with)
    log.info(
        "[plan][cycle %03d] challenger completed (%d critique(s))",
        state.cycle,
        len(raw_critiques),
    )

    # 3. Personas
    log.info(
        "[plan][cycle %03d] personas starting (%d persona(s), mode=%s)",
        state.cycle,
        len(ctx.config.personas),
        ctx.config.persona_mode,
    )
    emitter.transition(PlanState.PERSONAS, cycle=state.cycle)
    with ctx.audit_trail.step(
        "personas",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="plan",
    ):
        persona_critiques = strategy.run_personas(plan, ctx.call_with)
    log.info(
        "[plan][cycle %03d] personas completed (%d critique(s))",
        state.cycle,
        len(persona_critiques),
    )

    all_raw = raw_critiques + persona_critiques

    # 4. Verifier
    log.info(
        "[plan][cycle %03d] verifier starting (%d critique(s) to classify)",
        state.cycle,
        len(all_raw),
    )
    emitter.transition(PlanState.VERIFIER, cycle=state.cycle)
    with ctx.audit_trail.step(
        "verifier",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="plan",
    ):
        verified = strategy.run_verifier(plan, all_raw, ctx.call_with)
    log.info(
        "[plan][cycle %03d] verifier completed (%d classified critique(s))",
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
            "[plan][cycle %03d] human input required for %d critique(s)",
            state.cycle,
            len(human_required),
        )
        requests = _make_human_requests(human_required, state.cycle, state.issue_registry)
        state.pending_human_inputs = requests
        emitter.transition(PlanState.PAUSED_FOR_HUMAN, cycle=state.cycle)
        if interactive:
            from .hitl import collect_interactive
            decisions = collect_interactive(requests)
            state.human_decisions.extend(decisions)
            ctx.human_decisions.extend(decisions)
            state.pending_human_inputs = []

    # 7. Arbitrator — patches for VALID only
    log.info(
        "[plan][cycle %03d] arbitrator starting (%d valid critique(s))",
        state.cycle,
        len(valid),
    )
    emitter.transition(PlanState.ARBITRATOR, cycle=state.cycle)
    with ctx.audit_trail.step(
        "arbitrator",
        artifact_root=ctx.artifact_root,
        cycle=state.cycle,
        mode="plan",
    ):
        new_patches = strategy.run_arbitrator(plan, valid, ctx.call_with)
    state.pending_patches = new_patches
    log.info(
        "[plan][cycle %03d] arbitrator completed (%d patch(es))",
        state.cycle,
        len(new_patches),
    )

    # 8. Update issue registry
    # _register_issues only accesses state.issue_registry and state.cycle —
    # PlanCycleState is structurally compatible even though it is not a CycleState.
    _register_issues(state, verified)

    # 9. Update convergence counter
    _update_plan_convergence(
        state,
        valid_count=len(valid),
        human_required_count=len(human_required),
    )
    log.info(
        "[plan][cycle %03d] cycle complete (valid=%d stale=%d deferred=%d clean_streak=%d)",
        state.cycle,
        len(valid),
        len(stale),
        len(deferred),
        state.consecutive_clean_cycles,
    )

    state.current_workflow_state = emitter.current_state
    return len(valid), len(stale), len(deferred)
