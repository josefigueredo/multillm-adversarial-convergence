"""Implement domain package — MM12 Step 3.

Re-exports the implement / plan / document subsystem API under a single package
boundary.  Existing flat-module imports (``from src.implement_loop import …``)
remain valid.

Contexts exposed:
- Implement loop: target, config, task, patch, critique, cycle, validation
- Implement runner: runner orchestrator
- Implement strategy: strategy model
- Plan loop: plan cycle state, context, and runner
- Plan refiner: plan-mode HITL refiner
- Plan strategy: plan strategy model
- Document loop: issue, cycle state/context, and runner
- Document refiner: document-mode HITL refiner
- Document strategy: critique, patch, and convergence strategy models
"""

from __future__ import annotations

# ── Implement loop ─────────────────────────────────────────────────────────────
from ..implement_loop import (
    CandidatePatch,
    ImplementConfig,
    ImplementCritique,
    ImplementCycleContext,
    ImplementTask,
    ImplementTarget,
    TaskState,
    VerifiedImplementCritique,
    run_implement_cycle,
    validate_patch_boundaries,
)

# ── Implement runner ───────────────────────────────────────────────────────────
from ..implement_runner import ImplementRunner

# ── Implement strategy ─────────────────────────────────────────────────────────
from ..implement_strategy import ImplementStrategy

# ── Plan loop ─────────────────────────────────────────────────────────────────
from ..plan_loop import PlanCycleContext, PlanCycleState, run_plan_cycle

# ── Plan refiner ──────────────────────────────────────────────────────────────
from ..plan_refiner import PlanRefiner

# ── Plan strategy ─────────────────────────────────────────────────────────────
from ..plan_strategy import PlanStrategy

# ── Document loop ─────────────────────────────────────────────────────────────
from ..document_loop import CycleContext, CycleState, Issue, run_cycle

# ── Document refiner ──────────────────────────────────────────────────────────
from ..document_refiner import DocumentRefiner

# ── Document strategy ─────────────────────────────────────────────────────────
from ..document_strategy import ConvergeStrategy, Patch, RawCritique, VerifiedCritique

__all__ = [
    # implement loop
    "ImplementTarget",
    "ImplementConfig",
    "ImplementTask",
    "CandidatePatch",
    "ImplementCritique",
    "VerifiedImplementCritique",
    "TaskState",
    "ImplementCycleContext",
    "run_implement_cycle",
    "validate_patch_boundaries",
    # implement runner
    "ImplementRunner",
    # implement strategy
    "ImplementStrategy",
    # plan loop
    "PlanCycleState",
    "PlanCycleContext",
    "run_plan_cycle",
    # plan refiner
    "PlanRefiner",
    # plan strategy
    "PlanStrategy",
    # document loop
    "Issue",
    "CycleState",
    "CycleContext",
    "run_cycle",
    # document refiner
    "DocumentRefiner",
    # document strategy
    "RawCritique",
    "VerifiedCritique",
    "Patch",
    "ConvergeStrategy",
]
