"""Plan convergence loop — state types, context, and cycle execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import PlanConfig
from .document_loop import (
    Issue,
    _make_human_requests,
    _register_issues,
)
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .run_state import BaseContext


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


@dataclass
class PlanCycleContext(BaseContext):
    """Callback bundle for the plan loop.

    Extends ``BaseContext`` (call_with, invoke_for_strategy, track_usage,
    track_cost) with plan-specific state.
    """

    config: PlanConfig
    human_decisions: list[HumanDecision]
    update_issue_registry: Callable[[list[Any]], None]


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

    # 1. Builder — apply pending patches and produce revised plan
    plan = strategy.run_builder(
        state.plan,
        state.pending_patches,
        ctx.call_with,
        human_decisions=ctx.human_decisions,
    )
    state.plan = plan
    state.plan_versions.append(plan)
    state.pending_patches = []

    # 2. Challenger
    raw_critiques = strategy.run_challenger(plan, ctx.call_with)

    # 3. Personas
    persona_critiques = strategy.run_personas(plan, ctx.call_with)

    all_raw = raw_critiques + persona_critiques

    # 4. Verifier
    verified = strategy.run_verifier(plan, all_raw, ctx.call_with)

    # 5. Classify
    valid = [v for v in verified if v.status == "valid"]
    stale = [v for v in verified if v.status == "stale"]
    deferred = [v for v in verified if v.status == "deferred"]
    human_required = [
        v for v in deferred if v.defer_reason == DeferReason.HUMAN_REQUIRED
    ]

    # 6. HITL gate
    if human_required:
        requests = _make_human_requests(human_required, state.cycle, state.issue_registry)
        state.pending_human_inputs = requests
        if interactive:
            from .hitl import collect_interactive
            decisions = collect_interactive(requests)
            state.human_decisions.extend(decisions)
            ctx.human_decisions.extend(decisions)
            state.pending_human_inputs = []

    # 7. Arbitrator — patches for VALID only
    new_patches = strategy.run_arbitrator(plan, valid, ctx.call_with)
    state.pending_patches = new_patches

    # 8. Update issue registry
    _register_issues(state, verified)

    # 9. Update convergence counter
    _update_plan_convergence(
        state,
        valid_count=len(valid),
        human_required_count=len(human_required),
    )

    return len(valid), len(stale), len(deferred)
