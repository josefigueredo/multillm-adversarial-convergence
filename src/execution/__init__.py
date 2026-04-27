"""Execution domain package — MM12 Step 3.

Re-exports the MM10 execution subsystem API under a single package boundary:
execution plans, validation, diagnosis, integration adapters, and repair loops.
Existing flat-module imports (``from src.execution_plan import …``) remain valid.

Contexts exposed:
- Execution plans: step/context/plan models
- Validation: result and validation-result models, step/plan validators
- Diagnosis: artifact model, step/plan diagnosers, persistence
- Integration: adapters bridging loop state to the execution subsystem
- Repair: attempt/outcome/loop models
"""

from __future__ import annotations

# ── Execution plan ─────────────────────────────────────────────────────────────
from ..execution_plan import ExecutionPlan, ExecutionStep, TargetContext

# ── Validation ────────────────────────────────────────────────────────────────
from ..execution_validator import (
    ExecutionResult,
    ValidationResult,
    validate_plan,
    validate_step,
)

# ── Diagnosis ─────────────────────────────────────────────────────────────────
from ..execution_diagnosis import (
    DiagnosisArtifact,
    diagnose_plan,
    diagnose_step,
    persist_diagnosis,
)

# ── Integration adapters ──────────────────────────────────────────────────────
from ..execution_integration import (
    build_implement_execution_plan,
    build_research_execution_plan,
    diagnose_implement_failure,
    diagnose_research_failure,
    result_from_findings,
    result_from_implement_state,
)

# ── Repair loop ───────────────────────────────────────────────────────────────
from ..repair_loop import RepairAttempt, RepairLoop, RepairOutcome

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
