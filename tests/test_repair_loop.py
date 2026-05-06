"""Tests for Repair loop.

Covers:
- RepairAttempt: record of one repair cycle (before diagnosis, repaired plan,
  results/validations after)
- RepairOutcome: final outcome (resolved flag, attempts history, final state)
- RepairLoop.run(): inject repair_fn and execute_fn, stops on resolution or
  max_cycles, produces trustworthy RepairOutcome
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.execution.plan import ExecutionPlan, ExecutionStep, TargetContext
from src.execution.validator import ExecutionResult, ValidationResult, validate_step, validate_plan
from src.execution.diagnosis import DiagnosisArtifact, diagnose_plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(cmd="pytest", expected_exit_code=0, **kw):
    return ExecutionStep(command=cmd, expected_exit_code=expected_exit_code, **kw)


def _ctx(tmp_path):
    return TargetContext(working_dir=tmp_path)


def _plan(tmp_path, *steps):
    return ExecutionPlan(steps=steps or (_step(),), target=_ctx(tmp_path))


def _result(exit_code=0, stdout="ok", stderr=""):
    return ExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


def _failing_result():
    return ExecutionResult(exit_code=1, stdout="FAIL", stderr="")


# ---------------------------------------------------------------------------
# RepairAttempt
# ---------------------------------------------------------------------------

class TestRepairAttempt:
    def _make(self, tmp_path):
        from src.execution.repair_loop import RepairAttempt
        plan = _plan(tmp_path)
        results = [_result()]
        vrs = validate_plan(plan, results)
        diags = diagnose_plan(plan, results, vrs)
        return RepairAttempt(
            cycle=1,
            diagnosis=tuple(diags),
            repaired_plan=plan,
            results=tuple(results),
            validations=tuple(vrs),
        )

    def test_fields_accessible(self, tmp_path):
        from src.execution.repair_loop import RepairAttempt
        a = self._make(tmp_path)
        assert a.cycle == 1
        assert isinstance(a.diagnosis, tuple)
        assert isinstance(a.repaired_plan, ExecutionPlan)
        assert isinstance(a.results, tuple)
        assert isinstance(a.validations, tuple)

    def test_is_frozen(self, tmp_path):
        from src.execution.repair_loop import RepairAttempt
        a = self._make(tmp_path)
        with pytest.raises((AttributeError, TypeError)):
            a.cycle = 99  # type: ignore[misc]

    def test_to_dict_has_required_keys(self, tmp_path):
        from src.execution.repair_loop import RepairAttempt
        d = self._make(tmp_path).to_dict()
        assert "cycle" in d
        assert "diagnosis" in d
        assert "repaired_plan" in d
        assert "results" in d
        assert "validations" in d


# ---------------------------------------------------------------------------
# RepairOutcome
# ---------------------------------------------------------------------------

class TestRepairOutcome:
    def _make(self, tmp_path, resolved=True):
        from src.execution.repair_loop import RepairOutcome
        plan = _plan(tmp_path)
        results = [_result()]
        vrs = validate_plan(plan, results)
        return RepairOutcome(
            original_plan=plan,
            attempts=(),
            resolved=resolved,
            final_plan=plan,
            final_results=tuple(results),
            final_validations=tuple(vrs),
            cycles_run=0,
        )

    def test_fields_accessible(self, tmp_path):
        from src.execution.repair_loop import RepairOutcome
        o = self._make(tmp_path)
        assert isinstance(o.original_plan, ExecutionPlan)
        assert o.resolved is True
        assert o.cycles_run == 0

    def test_is_frozen(self, tmp_path):
        from src.execution.repair_loop import RepairOutcome
        o = self._make(tmp_path)
        with pytest.raises((AttributeError, TypeError)):
            o.resolved = False  # type: ignore[misc]

    def test_resolved_false_when_not_fixed(self, tmp_path):
        from src.execution.repair_loop import RepairOutcome
        o = self._make(tmp_path, resolved=False)
        assert o.resolved is False

    def test_to_dict_has_required_keys(self, tmp_path):
        from src.execution.repair_loop import RepairOutcome
        d = self._make(tmp_path).to_dict()
        assert "resolved" in d
        assert "cycles_run" in d
        assert "attempts" in d
        assert "final_plan" in d


# ---------------------------------------------------------------------------
# RepairLoop.run()
# ---------------------------------------------------------------------------

class TestRepairLoopRun:
    def _plan(self, tmp_path):
        return _plan(tmp_path, _step(expected_exit_code=0))

    def _passing_execute(self, plan):
        return [_result(exit_code=0)]

    def _failing_execute(self, plan):
        return [_failing_result()]

    def test_resolved_immediately_when_no_initial_failures(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        results = [_result()]
        vrs = validate_plan(plan, results)
        loop = RepairLoop(max_cycles=3)
        outcome = loop.run(plan, results, vrs,
                           repair_fn=MagicMock(), execute_fn=MagicMock())
        assert outcome.resolved is True
        assert outcome.cycles_run == 0

    def test_repair_fn_not_called_when_already_passing(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        results = [_result()]
        vrs = validate_plan(plan, results)
        repair_fn = MagicMock()
        RepairLoop(max_cycles=3).run(plan, results, vrs,
                                     repair_fn=repair_fn, execute_fn=MagicMock())
        repair_fn.assert_not_called()

    def test_resolves_after_one_repair(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        # repair_fn returns the same plan; execute_fn returns a passing result
        loop = RepairLoop(max_cycles=3)
        outcome = loop.run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=lambda p: [_result(exit_code=0)],
        )
        assert outcome.resolved is True
        assert outcome.cycles_run == 1

    def test_stops_at_max_cycles_when_never_resolved(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        loop = RepairLoop(max_cycles=2)
        outcome = loop.run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=lambda p: [_failing_result()],  # never fixes
        )
        assert outcome.resolved is False
        assert outcome.cycles_run == 2

    def test_attempts_recorded_in_outcome(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        loop = RepairLoop(max_cycles=2)
        outcome = loop.run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=lambda p: [_failing_result()],
        )
        assert len(outcome.attempts) == 2

    def test_repair_fn_called_with_diagnosis(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        received_diags = []
        def capture_repair(p, diags):
            received_diags.extend(diags)
            return p

        RepairLoop(max_cycles=1).run(
            plan, initial_results, initial_vrs,
            repair_fn=capture_repair,
            execute_fn=lambda p: [_result()],
        )
        assert len(received_diags) >= 1
        assert all(isinstance(d, DiagnosisArtifact) for d in received_diags)

    def test_execute_fn_called_with_repaired_plan(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        executed_plans = []
        def track_execute(p):
            executed_plans.append(p)
            return [_result()]

        RepairLoop(max_cycles=1).run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=track_execute,
        )
        assert len(executed_plans) == 1

    def test_final_plan_is_last_repaired_plan(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        loop = RepairLoop(max_cycles=1)
        outcome = loop.run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=lambda p: [_result()],
        )
        assert isinstance(outcome.final_plan, ExecutionPlan)

    def test_max_cycles_zero_raises(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        with pytest.raises(ValueError, match="max_cycles"):
            RepairLoop(max_cycles=0)

    def test_attempt_cycle_numbers_are_sequential(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = self._plan(tmp_path)
        initial_results = [_failing_result()]
        initial_vrs = validate_plan(plan, initial_results)

        outcome = RepairLoop(max_cycles=3).run(
            plan, initial_results, initial_vrs,
            repair_fn=lambda p, d: p,
            execute_fn=lambda p: [_failing_result()],
        )
        assert [a.cycle for a in outcome.attempts] == [1, 2, 3]

    def test_empty_results_for_nonempty_plan_raises(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = _plan(tmp_path, _step(), _step())
        with pytest.raises(ValueError, match="initial_results"):
            RepairLoop(max_cycles=1).run(
                plan, [], [],
                repair_fn=MagicMock(), execute_fn=MagicMock(),
            )

    def test_too_few_initial_results_raises(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = _plan(tmp_path, _step(), _step())
        result = _result()
        vr = validate_plan(_plan(tmp_path, _step()), [result])
        with pytest.raises(ValueError, match="initial_results"):
            RepairLoop(max_cycles=1).run(
                plan, [result], vr,
                repair_fn=MagicMock(), execute_fn=MagicMock(),
            )

    def test_too_few_initial_validations_raises(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = _plan(tmp_path, _step(), _step())
        results = [_result(), _result()]
        vr_one = validate_plan(_plan(tmp_path, _step()), [_result()])
        with pytest.raises(ValueError, match="initial_validations"):
            RepairLoop(max_cycles=1).run(
                plan, results, vr_one,
                repair_fn=MagicMock(), execute_fn=MagicMock(),
            )

    def test_matching_lengths_all_pass_resolves_immediately(self, tmp_path):
        from src.execution.repair_loop import RepairLoop
        plan = _plan(tmp_path, _step(), _step())
        results = [_result(), _result()]
        vrs = validate_plan(plan, results)
        outcome = RepairLoop(max_cycles=3).run(
            plan, results, vrs,
            repair_fn=MagicMock(), execute_fn=MagicMock(),
        )
        assert outcome.resolved is True
        assert outcome.cycles_run == 0
