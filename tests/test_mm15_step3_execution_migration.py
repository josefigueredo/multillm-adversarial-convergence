"""MM15 Step 3 — execution Phase A: canonical module paths + shim backward compat."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical new-path imports
# ---------------------------------------------------------------------------

class TestExecutionCanonicalPaths:
    def test_plan_module_importable_at_canonical_path(self):
        from src.execution import plan  # noqa: F401
        assert plan is not None

    def test_validator_module_importable_at_canonical_path(self):
        from src.execution import validator  # noqa: F401
        assert validator is not None

    def test_diagnosis_module_importable_at_canonical_path(self):
        from src.execution import diagnosis  # noqa: F401
        assert diagnosis is not None

    def test_integration_module_importable_at_canonical_path(self):
        from src.execution import integration  # noqa: F401
        assert integration is not None

    def test_repair_loop_module_importable_at_canonical_path(self):
        from src.execution import repair_loop  # noqa: F401
        assert repair_loop is not None

    def test_execution_plan_from_canonical_plan(self):
        from src.execution.plan import ExecutionPlan
        assert ExecutionPlan is not None

    def test_execution_step_from_canonical_plan(self):
        from src.execution.plan import ExecutionStep
        assert ExecutionStep is not None

    def test_validate_plan_from_canonical_validator(self):
        from src.execution.validator import validate_plan
        assert callable(validate_plan)

    def test_execution_result_from_canonical_validator(self):
        from src.execution.validator import ExecutionResult
        assert ExecutionResult is not None

    def test_diagnose_plan_from_canonical_diagnosis(self):
        from src.execution.diagnosis import diagnose_plan
        assert callable(diagnose_plan)

    def test_diagnosis_artifact_from_canonical_diagnosis(self):
        from src.execution.diagnosis import DiagnosisArtifact
        assert DiagnosisArtifact is not None

    def test_build_research_execution_plan_from_canonical_integration(self):
        from src.execution.integration import build_research_execution_plan
        assert callable(build_research_execution_plan)

    def test_repair_loop_class_from_canonical_repair_loop(self):
        from src.execution.repair_loop import RepairLoop
        assert RepairLoop is not None


# ---------------------------------------------------------------------------
# Old flat-path imports must still work via compatibility shims
# ---------------------------------------------------------------------------

class TestExecutionShimBackwardCompat:
    def test_execution_plan_from_src_execution_plan(self):
        from src.execution_plan import ExecutionPlan
        assert ExecutionPlan is not None

    def test_validate_plan_from_src_execution_validator(self):
        from src.execution_validator import validate_plan
        assert callable(validate_plan)

    def test_diagnose_plan_from_src_execution_diagnosis(self):
        from src.execution_diagnosis import diagnose_plan
        assert callable(diagnose_plan)

    def test_build_research_execution_plan_from_src_execution_integration(self):
        from src.execution_integration import build_research_execution_plan
        assert callable(build_research_execution_plan)

    def test_repair_loop_from_src_repair_loop(self):
        from src.repair_loop import RepairLoop
        assert RepairLoop is not None


# ---------------------------------------------------------------------------
# Regression: existing execution package __init__ API still intact
# ---------------------------------------------------------------------------

class TestExecutionPackageApiUnchanged:
    def test_execution_plan_via_execution_init(self):
        from src.execution import ExecutionPlan
        assert ExecutionPlan is not None

    def test_validate_plan_via_execution_init(self):
        from src.execution import validate_plan
        assert callable(validate_plan)

    def test_repair_loop_via_execution_init(self):
        from src.execution import RepairLoop
        assert RepairLoop is not None

    def test_build_research_execution_plan_via_execution_init(self):
        from src.execution import build_research_execution_plan
        assert callable(build_research_execution_plan)
