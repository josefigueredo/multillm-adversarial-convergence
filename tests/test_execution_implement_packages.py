"""MM12 Step 3 — execution and implement domain package seam tests.

TDD tests that verify:
- src.execution exposes the full execution subsystem API
- src.implement exposes the full implement/plan/document subsystem API
- Package __all__ entries are present and importable
"""
from __future__ import annotations

import importlib


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has(module, name: str) -> bool:
    return hasattr(importlib.import_module(module), name)


# ══════════════════════════════════════════════════════════════════════════════
# src.execution — MM10 execution subsystem
# ══════════════════════════════════════════════════════════════════════════════


class TestExecutionPackageImportable:
    def test_package_importable(self):
        import src.execution  # noqa: F401


class TestExecutionPlanTypes:
    def test_execution_step(self):
        from src.execution import ExecutionStep
        assert ExecutionStep is not None

    def test_target_context(self):
        from src.execution import TargetContext
        assert TargetContext is not None

    def test_execution_plan(self):
        from src.execution import ExecutionPlan
        assert ExecutionPlan is not None


class TestExecutionValidatorTypes:
    def test_execution_result(self):
        from src.execution import ExecutionResult
        assert ExecutionResult is not None

    def test_validation_result(self):
        from src.execution import ValidationResult
        assert ValidationResult is not None

    def test_validate_step(self):
        from src.execution import validate_step
        assert callable(validate_step)

    def test_validate_plan(self):
        from src.execution import validate_plan
        assert callable(validate_plan)


class TestExecutionDiagnosisTypes:
    def test_diagnosis_artifact(self):
        from src.execution import DiagnosisArtifact
        assert DiagnosisArtifact is not None

    def test_diagnose_step(self):
        from src.execution import diagnose_step
        assert callable(diagnose_step)

    def test_diagnose_plan(self):
        from src.execution import diagnose_plan
        assert callable(diagnose_plan)

    def test_persist_diagnosis(self):
        from src.execution import persist_diagnosis
        assert callable(persist_diagnosis)


class TestExecutionIntegrationFunctions:
    def test_build_implement_execution_plan(self):
        from src.execution import build_implement_execution_plan
        assert callable(build_implement_execution_plan)

    def test_result_from_implement_state(self):
        from src.execution import result_from_implement_state
        assert callable(result_from_implement_state)

    def test_diagnose_implement_failure(self):
        from src.execution import diagnose_implement_failure
        assert callable(diagnose_implement_failure)

    def test_build_research_execution_plan(self):
        from src.execution import build_research_execution_plan
        assert callable(build_research_execution_plan)

    def test_result_from_findings(self):
        from src.execution import result_from_findings
        assert callable(result_from_findings)

    def test_diagnose_research_failure(self):
        from src.execution import diagnose_research_failure
        assert callable(diagnose_research_failure)


class TestRepairLoopTypes:
    def test_repair_attempt(self):
        from src.execution import RepairAttempt
        assert RepairAttempt is not None

    def test_repair_outcome(self):
        from src.execution import RepairOutcome
        assert RepairOutcome is not None

    def test_repair_loop(self):
        from src.execution import RepairLoop
        assert RepairLoop is not None


class TestExecutionAllList:
    def test_all_defined(self):
        import src.execution as pkg
        assert hasattr(pkg, "__all__")

    def test_all_members_importable(self):
        import src.execution as pkg
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"src.execution.__all__ lists {name!r} but it is not present"


# ══════════════════════════════════════════════════════════════════════════════
# src.implement — implement / plan / document subsystems
# ══════════════════════════════════════════════════════════════════════════════


class TestImplementPackageImportable:
    def test_package_importable(self):
        import src.implement  # noqa: F401


class TestImplementLoopTypes:
    def test_implement_target(self):
        from src.implement import ImplementTarget
        assert ImplementTarget is not None

    def test_implement_config(self):
        from src.implement import ImplementConfig
        assert ImplementConfig is not None

    def test_implement_task(self):
        from src.implement import ImplementTask
        assert ImplementTask is not None

    def test_candidate_patch(self):
        from src.implement import CandidatePatch
        assert CandidatePatch is not None

    def test_implement_critique(self):
        from src.implement import ImplementCritique
        assert ImplementCritique is not None

    def test_verified_implement_critique(self):
        from src.implement import VerifiedImplementCritique
        assert VerifiedImplementCritique is not None

    def test_task_state(self):
        from src.implement import TaskState
        assert TaskState is not None

    def test_implement_cycle_context(self):
        from src.implement import ImplementCycleContext
        assert ImplementCycleContext is not None

    def test_run_implement_cycle(self):
        from src.implement import run_implement_cycle
        assert callable(run_implement_cycle)

    def test_validate_patch_boundaries(self):
        from src.implement import validate_patch_boundaries
        assert callable(validate_patch_boundaries)


class TestImplementRunnerTypes:
    def test_implement_runner(self):
        from src.implement import ImplementRunner
        assert ImplementRunner is not None


class TestImplementStrategyTypes:
    def test_implement_strategy(self):
        from src.implement import ImplementStrategy
        assert ImplementStrategy is not None


class TestPlanLoopTypes:
    def test_plan_cycle_state(self):
        from src.implement import PlanCycleState
        assert PlanCycleState is not None

    def test_plan_cycle_context(self):
        from src.implement import PlanCycleContext
        assert PlanCycleContext is not None

    def test_run_plan_cycle(self):
        from src.implement import run_plan_cycle
        assert callable(run_plan_cycle)


class TestPlanRefinerTypes:
    def test_plan_refiner(self):
        from src.implement import PlanRefiner
        assert PlanRefiner is not None


class TestPlanStrategyTypes:
    def test_plan_strategy(self):
        from src.implement import PlanStrategy
        assert PlanStrategy is not None


class TestDocumentLoopTypes:
    def test_issue(self):
        from src.implement import Issue
        assert Issue is not None

    def test_cycle_state(self):
        from src.implement import CycleState
        assert CycleState is not None

    def test_cycle_context(self):
        from src.implement import CycleContext
        assert CycleContext is not None

    def test_run_cycle(self):
        from src.implement import run_cycle
        assert callable(run_cycle)


class TestDocumentRefinerTypes:
    def test_document_refiner(self):
        from src.implement import DocumentRefiner
        assert DocumentRefiner is not None


class TestDocumentStrategyTypes:
    def test_raw_critique(self):
        from src.implement import RawCritique
        assert RawCritique is not None

    def test_verified_critique(self):
        from src.implement import VerifiedCritique
        assert VerifiedCritique is not None

    def test_patch(self):
        from src.implement import Patch
        assert Patch is not None

    def test_converge_strategy(self):
        from src.implement import ConvergeStrategy
        assert ConvergeStrategy is not None


class TestImplementAllList:
    def test_all_defined(self):
        import src.implement as pkg
        assert hasattr(pkg, "__all__")

    def test_all_members_importable(self):
        import src.implement as pkg
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"src.implement.__all__ lists {name!r} but it is not present"


