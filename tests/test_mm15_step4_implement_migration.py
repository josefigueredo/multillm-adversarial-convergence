"""MM15 Step 4 — implement Phase A: canonical module paths + shim backward compat."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical new-path imports
# ---------------------------------------------------------------------------

class TestImplementCanonicalPaths:
    def test_implement_loop_module_importable_at_canonical_path(self):
        from src.implement import implement_loop  # noqa: F401
        assert implement_loop is not None

    def test_implement_runner_module_importable_at_canonical_path(self):
        from src.implement import implement_runner  # noqa: F401
        assert implement_runner is not None

    def test_implement_strategy_module_importable_at_canonical_path(self):
        from src.implement import implement_strategy  # noqa: F401
        assert implement_strategy is not None

    def test_plan_loop_module_importable_at_canonical_path(self):
        from src.implement import plan_loop  # noqa: F401
        assert plan_loop is not None

    def test_plan_refiner_module_importable_at_canonical_path(self):
        from src.implement import plan_refiner  # noqa: F401
        assert plan_refiner is not None

    def test_plan_strategy_module_importable_at_canonical_path(self):
        from src.implement import plan_strategy  # noqa: F401
        assert plan_strategy is not None

    def test_document_loop_module_importable_at_canonical_path(self):
        from src.implement import document_loop  # noqa: F401
        assert document_loop is not None

    def test_document_refiner_module_importable_at_canonical_path(self):
        from src.implement import document_refiner  # noqa: F401
        assert document_refiner is not None

    def test_document_strategy_module_importable_at_canonical_path(self):
        from src.implement import document_strategy  # noqa: F401
        assert document_strategy is not None

    def test_implement_target_from_canonical_implement_loop(self):
        from src.implement.implement_loop import ImplementTarget
        assert ImplementTarget is not None

    def test_run_implement_cycle_from_canonical_implement_loop(self):
        from src.implement.implement_loop import run_implement_cycle
        assert callable(run_implement_cycle)

    def test_implement_runner_class_from_canonical(self):
        from src.implement.implement_runner import ImplementRunner
        assert ImplementRunner is not None

    def test_plan_cycle_state_from_canonical_plan_loop(self):
        from src.implement.plan_loop import PlanCycleState
        assert PlanCycleState is not None

    def test_document_strategy_converge_from_canonical(self):
        from src.implement.document_strategy import ConvergeStrategy
        assert ConvergeStrategy is not None


# ---------------------------------------------------------------------------
# Old flat-path imports must still work via compatibility shims
# ---------------------------------------------------------------------------

class TestImplementShimBackwardCompat:
    def test_implement_target_from_src_implement_loop(self):
        from src.implement_loop import ImplementTarget
        assert ImplementTarget is not None

    def test_implement_runner_from_src_implement_runner(self):
        from src.implement_runner import ImplementRunner
        assert ImplementRunner is not None

    def test_plan_cycle_state_from_src_plan_loop(self):
        from src.plan_loop import PlanCycleState
        assert PlanCycleState is not None

    def test_plan_refiner_from_src_plan_refiner(self):
        from src.plan_refiner import PlanRefiner
        assert PlanRefiner is not None

    def test_plan_strategy_from_src_plan_strategy(self):
        from src.plan_strategy import PlanStrategy
        assert PlanStrategy is not None

    def test_document_refiner_from_src_document_refiner(self):
        from src.document_refiner import DocumentRefiner
        assert DocumentRefiner is not None

    def test_converge_strategy_from_src_document_strategy(self):
        from src.document_strategy import ConvergeStrategy
        assert ConvergeStrategy is not None


# ---------------------------------------------------------------------------
# Regression: existing implement package __init__ API still intact
# ---------------------------------------------------------------------------

class TestImplementPackageApiUnchanged:
    def test_implement_target_via_implement_init(self):
        from src.implement import ImplementTarget
        assert ImplementTarget is not None

    def test_run_implement_cycle_via_implement_init(self):
        from src.implement import run_implement_cycle
        assert callable(run_implement_cycle)

    def test_plan_refiner_via_implement_init(self):
        from src.implement import PlanRefiner
        assert PlanRefiner is not None

    def test_document_refiner_via_implement_init(self):
        from src.implement import DocumentRefiner
        assert DocumentRefiner is not None
