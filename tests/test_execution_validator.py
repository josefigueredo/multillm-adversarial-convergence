"""Tests for MM10 Step 2 — Execution validator layer.

Covers:
- ExecutionResult: captured output from a real or simulated step execution
- ValidationResult: outcome of validating one result against one step's expectations
- validate_step(): exit code, output patterns, timeout checks
- validate_plan(): validates all steps in a plan, returns list of results
- Pure functions — no I/O, no side effects
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.execution_plan import ExecutionStep, ExecutionPlan, TargetContext


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_fields_accessible(self):
        from src.execution_validator import ExecutionResult
        r = ExecutionResult(exit_code=0, stdout="ok", stderr="")
        assert r.exit_code == 0
        assert r.stdout == "ok"
        assert r.stderr == ""

    def test_timed_out_defaults_false(self):
        from src.execution_validator import ExecutionResult
        assert ExecutionResult(exit_code=0, stdout="", stderr="").timed_out is False

    def test_timed_out_configurable(self):
        from src.execution_validator import ExecutionResult
        assert ExecutionResult(exit_code=124, stdout="", stderr="", timed_out=True).timed_out is True

    def test_duration_defaults_none(self):
        from src.execution_validator import ExecutionResult
        assert ExecutionResult(exit_code=0, stdout="", stderr="").duration_seconds is None

    def test_duration_configurable(self):
        from src.execution_validator import ExecutionResult
        r = ExecutionResult(exit_code=0, stdout="", stderr="", duration_seconds=1.5)
        assert r.duration_seconds == 1.5

    def test_is_frozen(self):
        from src.execution_validator import ExecutionResult
        r = ExecutionResult(exit_code=0, stdout="", stderr="")
        with pytest.raises((AttributeError, TypeError)):
            r.exit_code = 1  # type: ignore[misc]

    def test_to_dict_round_trip(self):
        from src.execution_validator import ExecutionResult
        r = ExecutionResult(exit_code=1, stdout="out", stderr="err", timed_out=False, duration_seconds=2.0)
        restored = ExecutionResult.from_dict(r.to_dict())
        assert restored.exit_code == 1
        assert restored.stdout == "out"
        assert restored.duration_seconds == 2.0


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def _step(self, **kw):
        return ExecutionStep(command="pytest", **kw)

    def test_passed_when_no_failures(self):
        from src.execution_validator import ValidationResult
        r = ValidationResult(step=self._step(), failures=())
        assert r.passed is True

    def test_failed_when_failures_present(self):
        from src.execution_validator import ValidationResult
        r = ValidationResult(step=self._step(), failures=("exit code mismatch",))
        assert r.passed is False

    def test_step_accessible(self):
        from src.execution_validator import ValidationResult
        s = self._step()
        r = ValidationResult(step=s, failures=())
        assert r.step is s

    def test_failures_tuple(self):
        from src.execution_validator import ValidationResult
        r = ValidationResult(step=self._step(), failures=("a", "b"))
        assert len(r.failures) == 2

    def test_is_frozen(self):
        from src.execution_validator import ValidationResult
        r = ValidationResult(step=self._step(), failures=())
        with pytest.raises((AttributeError, TypeError)):
            r.failures = ("x",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# validate_step()
# ---------------------------------------------------------------------------

class TestValidateStep:
    def _step(self, **kw):
        return ExecutionStep(command="pytest", **kw)

    def _result(self, **kw):
        from src.execution_validator import ExecutionResult
        defaults = dict(exit_code=0, stdout="", stderr="")
        defaults.update(kw)
        return ExecutionResult(**defaults)

    def test_passing_step_returns_passed_true(self):
        from src.execution_validator import validate_step
        result = validate_step(self._step(), self._result(exit_code=0))
        assert result.passed is True

    def test_wrong_exit_code_fails(self):
        from src.execution_validator import validate_step
        result = validate_step(self._step(expected_exit_code=0), self._result(exit_code=1))
        assert result.passed is False

    def test_wrong_exit_code_failure_message_contains_codes(self):
        from src.execution_validator import validate_step
        result = validate_step(self._step(expected_exit_code=0), self._result(exit_code=2))
        assert any("exit" in f.lower() for f in result.failures)

    def test_correct_exit_code_not_a_failure(self):
        from src.execution_validator import validate_step
        result = validate_step(self._step(expected_exit_code=1), self._result(exit_code=1))
        assert result.passed is True

    def test_missing_output_pattern_fails(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=("PASS",))
        result = validate_step(step, self._result(stdout="FAIL"))
        assert result.passed is False

    def test_present_output_pattern_passes(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=("PASS",))
        result = validate_step(step, self._result(stdout="3 PASS 0 FAIL"))
        assert result.passed is True

    def test_output_pattern_matched_in_stderr_too(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=("WARNING",))
        result = validate_step(step, self._result(stdout="", stderr="WARNING: something"))
        assert result.passed is True

    def test_multiple_patterns_all_must_match(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=("passed", "no errors"))
        result = validate_step(step, self._result(stdout="3 passed"))
        assert result.passed is False  # "no errors" missing

    def test_timed_out_always_fails(self):
        from src.execution_validator import validate_step
        step = self._step()
        result = validate_step(step, self._result(exit_code=0, timed_out=True))
        assert result.passed is False

    def test_timed_out_failure_message_mentions_timeout(self):
        from src.execution_validator import validate_step
        result = validate_step(self._step(), self._result(exit_code=0, timed_out=True))
        assert any("timeout" in f.lower() or "timed" in f.lower() for f in result.failures)

    def test_no_patterns_means_no_pattern_check(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=())
        result = validate_step(step, self._result(stdout="anything goes"))
        assert result.passed is True

    def test_missing_pattern_failure_names_pattern(self):
        from src.execution_validator import validate_step
        step = self._step(expected_output_patterns=("unique_token",))
        result = validate_step(step, self._result(stdout="nothing here"))
        assert any("unique_token" in f for f in result.failures)

    def test_multiple_failures_collected(self):
        from src.execution_validator import validate_step
        step = self._step(expected_exit_code=0, expected_output_patterns=("PASS",), timeout_seconds=5)
        result = validate_step(step, self._result(exit_code=1, stdout="FAIL", timed_out=True))
        assert len(result.failures) >= 2


# ---------------------------------------------------------------------------
# validate_plan()
# ---------------------------------------------------------------------------

class TestValidatePlan:
    def _ctx(self, tmp_path):
        return TargetContext(working_dir=tmp_path)

    def _result(self, exit_code=0, stdout="", stderr="", timed_out=False):
        from src.execution_validator import ExecutionResult
        return ExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=timed_out)

    def test_returns_list_of_validation_results(self, tmp_path):
        from src.execution_validator import ExecutionResult, validate_plan
        plan = ExecutionPlan(
            steps=(ExecutionStep(command="pytest"),),
            target=self._ctx(tmp_path),
        )
        results = validate_plan(plan, [self._result()])
        assert isinstance(results, list)
        assert len(results) == 1

    def test_all_pass_returns_all_passed(self, tmp_path):
        from src.execution_validator import validate_plan
        plan = ExecutionPlan(
            steps=(ExecutionStep(command="a"), ExecutionStep(command="b")),
            target=self._ctx(tmp_path),
        )
        vr = validate_plan(plan, [self._result(), self._result()])
        assert all(r.passed for r in vr)

    def test_one_fail_returns_one_failed(self, tmp_path):
        from src.execution_validator import validate_plan
        plan = ExecutionPlan(
            steps=(ExecutionStep(command="a", expected_exit_code=0),),
            target=self._ctx(tmp_path),
        )
        vr = validate_plan(plan, [self._result(exit_code=1)])
        assert not vr[0].passed

    def test_mismatched_results_count_raises(self, tmp_path):
        from src.execution_validator import validate_plan
        plan = ExecutionPlan(
            steps=(ExecutionStep(command="a"), ExecutionStep(command="b")),
            target=self._ctx(tmp_path),
        )
        with pytest.raises(ValueError, match="results"):
            validate_plan(plan, [self._result()])  # only 1 result for 2 steps

    def test_results_correspond_to_steps_in_order(self, tmp_path):
        from src.execution_validator import validate_plan
        plan = ExecutionPlan(
            steps=(
                ExecutionStep(command="ok", expected_exit_code=0),
                ExecutionStep(command="bad", expected_exit_code=0),
            ),
            target=self._ctx(tmp_path),
        )
        vr = validate_plan(plan, [self._result(exit_code=0), self._result(exit_code=1)])
        assert vr[0].passed is True
        assert vr[1].passed is False
