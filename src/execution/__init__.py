"""Execution domain package.

Re-exports the MM10 execution subsystem API under a single package boundary:
execution plans, validation, diagnosis, integration adapters, and repair loops.
Canonical paths are ``src.execution.<module>``; flat-module imports were
removed in MM15 Step 7.

Contexts exposed:
- Execution plans: step/context/plan models
- Validation: result and validation-result models, step/plan validators
- Diagnosis: artifact model, step/plan diagnosers, persistence
- Integration: adapters bridging loop state to the execution subsystem
- Repair: attempt/outcome/loop models
"""

from __future__ import annotations

# ── Execution plan ─────────────────────────────────────────────────────────────
from .plan import ExecutionPlan, ExecutionStep, TargetContext

# ── Validation ────────────────────────────────────────────────────────────────
from .validator import (
    ExecutionResult,
    ValidationResult,
    validate_plan,
    validate_step,
)

# ── Diagnosis ─────────────────────────────────────────────────────────────────
from .diagnosis import (
    DiagnosisArtifact,
    diagnose_plan,
    diagnose_step,
    persist_diagnosis,
)

# ── Integration adapters ──────────────────────────────────────────────────────
from .integration import (
    build_implement_execution_plan,
    build_research_execution_plan,
    diagnose_implement_failure,
    diagnose_research_failure,
    result_from_findings,
    result_from_implement_state,
)

# ── Repair loop ───────────────────────────────────────────────────────────────
from .repair_loop import RepairAttempt, RepairLoop, RepairOutcome

__all__ = [
    # execution plan
    "ExecutionStep",
    "TargetContext",
    "ExecutionPlan",
    # validation
    "ExecutionResult",
    "ValidationResult",
    "validate_step",
    "validate_plan",
    # diagnosis
    "DiagnosisArtifact",
    "diagnose_step",
    "diagnose_plan",
    "persist_diagnosis",
    # integration
    "build_implement_execution_plan",
    "result_from_implement_state",
    "diagnose_implement_failure",
    "build_research_execution_plan",
    "result_from_findings",
    "diagnose_research_failure",
    # repair
    "RepairAttempt",
    "RepairOutcome",
    "RepairLoop",
]
