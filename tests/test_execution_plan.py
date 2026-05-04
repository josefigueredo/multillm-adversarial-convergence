"""Tests for MM10 Step 1 — Execution plan model.

Covers:
- ExecutionStep: command/tool spec, expectations, frozen contract
- ExecutionPlan: ordered steps, target context, frozen, validation
- TargetContext: describes execution environment
- Serialisation: to/from dict for artifact persistence
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# ExecutionStep
# ---------------------------------------------------------------------------

class TestExecutionStep:
    def test_fields_accessible(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="pytest src/", description="run unit tests")
        assert step.command == "pytest src/"
        assert step.description == "run unit tests"

    def test_default_expected_exit_code_zero(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="make build")
        assert step.expected_exit_code == 0

    def test_expected_exit_code_configurable(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="bad", expected_exit_code=1)
        assert step.expected_exit_code == 1

    def test_default_timeout_none(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="echo hi")
        assert step.timeout_seconds is None

    def test_timeout_configurable(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="long task", timeout_seconds=60)
        assert step.timeout_seconds == 60

    def test_expected_output_patterns_default_empty(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="pytest")
        assert step.expected_output_patterns == ()

    def test_expected_output_patterns_configurable(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="pytest", expected_output_patterns=("passed",))
        assert "passed" in step.expected_output_patterns

    def test_is_frozen(self):
        from src.execution.plan import ExecutionStep
        step = ExecutionStep(command="pytest")
        with pytest.raises((AttributeError, TypeError)):
            step.command = "other"  # type: ignore[misc]

    def test_to_dict_has_required_fields(self):
        from src.execution.plan import ExecutionStep
        d = ExecutionStep(command="make test", description="tests").to_dict()
        assert d["command"] == "make test"
        assert d["description"] == "tests"
        assert "expected_exit_code" in d

    def test_from_dict_round_trips(self):
        from src.execution.plan import ExecutionStep
        original = ExecutionStep(
            command="npm test",
            description="JS tests",
            expected_exit_code=0,
            timeout_seconds=120,
            expected_output_patterns=("PASS",),
        )
        restored = ExecutionStep.from_dict(original.to_dict())
        assert restored.command == original.command
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.expected_output_patterns == original.expected_output_patterns


# ---------------------------------------------------------------------------
# TargetContext
# ---------------------------------------------------------------------------

class TestTargetContext:
    def test_fields_accessible(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path)
        assert ctx.working_dir == tmp_path

    def test_env_vars_default_empty(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path)
        assert ctx.env_vars == {}

    def test_env_vars_configurable(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path, env_vars={"CI": "true"})
        assert ctx.env_vars["CI"] == "true"

    def test_description_default_empty(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path)
        assert ctx.description == ""

    def test_is_frozen(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path)
        with pytest.raises((AttributeError, TypeError)):
            ctx.description = "changed"  # type: ignore[misc]

    def test_to_dict_has_working_dir(self, tmp_path):
        from src.execution.plan import TargetContext
        d = TargetContext(working_dir=tmp_path).to_dict()
        assert str(tmp_path) in d["working_dir"]

    def test_from_dict_round_trips(self, tmp_path):
        from src.execution.plan import TargetContext
        original = TargetContext(
            working_dir=tmp_path, env_vars={"X": "1"}, description="test env"
        )
        restored = TargetContext.from_dict(original.to_dict())
        assert restored.working_dir == tmp_path
        assert restored.env_vars == {"X": "1"}
        assert restored.description == "test env"


# ---------------------------------------------------------------------------
# ExecutionPlan
# ---------------------------------------------------------------------------

class TestExecutionPlan:
    def _step(self, cmd="pytest"):
        from src.execution.plan import ExecutionStep
        return ExecutionStep(command=cmd)

    def _ctx(self, tmp_path):
        from src.execution.plan import TargetContext
        return TargetContext(working_dir=tmp_path)

    def test_steps_and_target_accessible(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        plan = ExecutionPlan(steps=(self._step(),), target=self._ctx(tmp_path))
        assert len(plan.steps) == 1
        assert plan.target.working_dir == tmp_path

    def test_empty_steps_raises(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        with pytest.raises(ValueError, match="steps"):
            ExecutionPlan(steps=(), target=self._ctx(tmp_path))

    def test_description_default_empty(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        plan = ExecutionPlan(steps=(self._step(),), target=self._ctx(tmp_path))
        assert plan.description == ""

    def test_description_configurable(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        plan = ExecutionPlan(steps=(self._step(),), target=self._ctx(tmp_path), description="CI suite")
        assert plan.description == "CI suite"

    def test_is_frozen(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        plan = ExecutionPlan(steps=(self._step(),), target=self._ctx(tmp_path))
        with pytest.raises((AttributeError, TypeError)):
            plan.description = "x"  # type: ignore[misc]

    def test_multiple_steps_preserved_in_order(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        s1 = self._step("step1")
        s2 = self._step("step2")
        plan = ExecutionPlan(steps=(s1, s2), target=self._ctx(tmp_path))
        assert plan.steps[0].command == "step1"
        assert plan.steps[1].command == "step2"

    def test_to_dict_has_steps_and_target(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        d = ExecutionPlan(steps=(self._step(),), target=self._ctx(tmp_path)).to_dict()
        assert "steps" in d
        assert "target" in d
        assert isinstance(d["steps"], list)

    def test_from_dict_round_trips(self, tmp_path):
        from src.execution.plan import ExecutionPlan
        original = ExecutionPlan(
            steps=(self._step("make lint"), self._step("make test")),
            target=self._ctx(tmp_path),
            description="build pipeline",
        )
        restored = ExecutionPlan.from_dict(original.to_dict())
        assert len(restored.steps) == 2
        assert restored.steps[0].command == "make lint"
        assert restored.description == "build pipeline"
        assert restored.target.working_dir == tmp_path

    def test_working_dir_must_exist(self, tmp_path):
        from src.execution.plan import ExecutionPlan, ExecutionStep, TargetContext
        phantom = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="working_dir"):
            ExecutionPlan(
                steps=(ExecutionStep(command="x"),),
                target=TargetContext(working_dir=phantom),
            )


# ---------------------------------------------------------------------------
# MM10 Step 1 refinement — TargetContext deep immutability
# ---------------------------------------------------------------------------

class TestTargetContextImmutability:
    def test_env_vars_cannot_be_mutated_after_construction(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path, env_vars={"A": "1"})
        with pytest.raises((TypeError, AttributeError)):
            ctx.env_vars["B"] = "2"  # type: ignore[index]

    def test_env_vars_readable_as_mapping(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path, env_vars={"X": "hello"})
        assert ctx.env_vars["X"] == "hello"

    def test_env_vars_keys_iterable(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path, env_vars={"A": "1", "B": "2"})
        assert set(ctx.env_vars.keys()) == {"A", "B"}

    def test_source_dict_mutation_does_not_affect_context(self, tmp_path):
        from src.execution.plan import TargetContext
        original = {"X": "before"}
        ctx = TargetContext(working_dir=tmp_path, env_vars=original)
        original["X"] = "after"
        assert ctx.env_vars["X"] == "before"

    def test_round_trip_preserves_env_vars(self, tmp_path):
        from src.execution.plan import TargetContext
        ctx = TargetContext(working_dir=tmp_path, env_vars={"CI": "true", "PORT": "8080"})
        restored = TargetContext.from_dict(ctx.to_dict())
        assert restored.env_vars["CI"] == "true"
        assert restored.env_vars["PORT"] == "8080"

    def test_execution_plan_target_env_vars_immutable(self, tmp_path):
        from src.execution.plan import ExecutionPlan, ExecutionStep, TargetContext
        plan = ExecutionPlan(
            steps=(ExecutionStep(command="pytest"),),
            target=TargetContext(working_dir=tmp_path, env_vars={"K": "v"}),
        )
        with pytest.raises((TypeError, AttributeError)):
            plan.target.env_vars["EXTRA"] = "injected"  # type: ignore[index]
