"""Tests for MM10 Step 3 — Diagnosis artifacts.

Covers:
- DiagnosisArtifact: rich frozen record of a validation failure
- diagnose_step(): returns None on pass, artifact on fail
- diagnose_plan(): returns one artifact per failed step only
- persist_diagnosis(): writes diagnosis.json to output directory
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.execution_plan import ExecutionStep, ExecutionPlan, TargetContext
from src.execution_validator import ExecutionResult, ValidationResult, validate_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passing_result(exit_code=0, stdout="ok", stderr=""):
    return ExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


def _failing_result(exit_code=1, stdout="FAIL", stderr=""):
    return ExecutionResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


def _step(**kw):
    return ExecutionStep(command="pytest", **kw)


def _ctx(tmp_path):
    return TargetContext(working_dir=tmp_path)


# ---------------------------------------------------------------------------
# DiagnosisArtifact
# ---------------------------------------------------------------------------

class TestDiagnosisArtifact:
    def _vr_fail(self):
        s = _step(expected_exit_code=0)
        r = _failing_result(exit_code=1)
        return s, r, validate_step(s, r)

    def test_fields_accessible(self):
        from src.execution_diagnosis import DiagnosisArtifact
        s, r, vr = self._vr_fail()
        artifact = DiagnosisArtifact(step=s, result=r, validation=vr,
                                     diagnosis_type="exit_code_mismatch", summary="bad exit")
        assert artifact.step is s
        assert artifact.result is r
        assert artifact.validation is vr
        assert artifact.diagnosis_type == "exit_code_mismatch"
        assert artifact.summary == "bad exit"

    def test_is_frozen(self):
        from src.execution_diagnosis import DiagnosisArtifact
        s, r, vr = self._vr_fail()
        artifact = DiagnosisArtifact(step=s, result=r, validation=vr,
                                     diagnosis_type="exit_code_mismatch", summary="x")
        with pytest.raises((AttributeError, TypeError)):
            artifact.summary = "changed"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        from src.execution_diagnosis import DiagnosisArtifact
        s, r, vr = self._vr_fail()
        d = DiagnosisArtifact(step=s, result=r, validation=vr,
                               diagnosis_type="exit_code_mismatch", summary="bad").to_dict()
        assert "step" in d
        assert "result" in d
        assert "diagnosis_type" in d
        assert "summary" in d
        assert "failures" in d

    def test_from_dict_round_trips(self):
        from src.execution_diagnosis import DiagnosisArtifact
        s, r, vr = self._vr_fail()
        original = DiagnosisArtifact(step=s, result=r, validation=vr,
                                      diagnosis_type="exit_code_mismatch", summary="bad exit")
        restored = DiagnosisArtifact.from_dict(original.to_dict())
        assert restored.step.command == s.command
        assert restored.result.exit_code == r.exit_code
        assert restored.diagnosis_type == "exit_code_mismatch"
        assert restored.summary == "bad exit"


# ---------------------------------------------------------------------------
# diagnose_step()
# ---------------------------------------------------------------------------

class TestDiagnoseStep:
    def test_returns_none_for_passing_validation(self):
        from src.execution_diagnosis import diagnose_step
        s = _step()
        r = _passing_result()
        vr = validate_step(s, r)
        assert diagnose_step(s, r, vr) is None

    def test_returns_artifact_for_failed_validation(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(expected_exit_code=0)
        r = _failing_result(exit_code=1)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None

    def test_timeout_diagnosis_type(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(timeout_seconds=5)
        r = ExecutionResult(exit_code=0, stdout="", stderr="", timed_out=True)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert artifact.diagnosis_type == "timeout"

    def test_exit_code_mismatch_diagnosis_type(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(expected_exit_code=0)
        r = _failing_result(exit_code=2)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert artifact.diagnosis_type == "exit_code_mismatch"

    def test_pattern_missing_diagnosis_type(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(expected_output_patterns=("PASS",))
        r = _passing_result(stdout="FAIL")
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert artifact.diagnosis_type == "pattern_missing"

    def test_multiple_failures_diagnosis_type(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(expected_exit_code=0, expected_output_patterns=("PASS",))
        r = ExecutionResult(exit_code=1, stdout="FAIL", stderr="", timed_out=True)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert artifact.diagnosis_type == "multiple"

    def test_summary_is_non_empty(self):
        from src.execution_diagnosis import diagnose_step
        s = _step(expected_exit_code=0)
        r = _failing_result(exit_code=1)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert len(artifact.summary) > 0

    def test_summary_mentions_command(self):
        from src.execution_diagnosis import diagnose_step
        s = ExecutionStep(command="make test", expected_exit_code=0)
        r = _failing_result(exit_code=1)
        vr = validate_step(s, r)
        artifact = diagnose_step(s, r, vr)
        assert artifact is not None
        assert "make test" in artifact.summary


# ---------------------------------------------------------------------------
# diagnose_plan()
# ---------------------------------------------------------------------------

class TestDiagnosePlan:
    def _plan(self, tmp_path, *steps):
        return ExecutionPlan(steps=steps, target=_ctx(tmp_path))

    def test_returns_empty_list_when_all_pass(self, tmp_path):
        from src.execution_diagnosis import diagnose_plan
        from src.execution_validator import validate_plan
        plan = self._plan(tmp_path, _step(), _step())
        results = [_passing_result(), _passing_result()]
        vrs = validate_plan(plan, results)
        assert diagnose_plan(plan, results, vrs) == []

    def test_returns_one_artifact_per_failed_step(self, tmp_path):
        from src.execution_diagnosis import diagnose_plan
        from src.execution_validator import validate_plan
        plan = self._plan(tmp_path,
                          _step(expected_exit_code=0),
                          _step(expected_exit_code=0))
        results = [_passing_result(), _failing_result(exit_code=1)]
        vrs = validate_plan(plan, results)
        artifacts = diagnose_plan(plan, results, vrs)
        assert len(artifacts) == 1

    def test_does_not_include_passing_steps(self, tmp_path):
        from src.execution_diagnosis import diagnose_plan
        from src.execution_validator import validate_plan
        plan = self._plan(tmp_path, _step(), _step(expected_exit_code=0))
        results = [_passing_result(), _failing_result(exit_code=1)]
        vrs = validate_plan(plan, results)
        artifacts = diagnose_plan(plan, results, vrs)
        assert all(not a.validation.passed for a in artifacts)

    def test_all_failing_returns_all_artifacts(self, tmp_path):
        from src.execution_diagnosis import diagnose_plan
        from src.execution_validator import validate_plan
        plan = self._plan(tmp_path, _step(expected_exit_code=0), _step(expected_exit_code=0))
        results = [_failing_result(exit_code=1), _failing_result(exit_code=2)]
        vrs = validate_plan(plan, results)
        artifacts = diagnose_plan(plan, results, vrs)
        assert len(artifacts) == 2


# ---------------------------------------------------------------------------
# persist_diagnosis()
# ---------------------------------------------------------------------------

class TestPersistDiagnosis:
    def _artifact(self):
        from src.execution_diagnosis import DiagnosisArtifact
        s = _step(expected_exit_code=0)
        r = _failing_result(exit_code=1)
        vr = validate_step(s, r)
        return DiagnosisArtifact(step=s, result=r, validation=vr,
                                  diagnosis_type="exit_code_mismatch", summary="failed")

    def test_writes_diagnosis_json(self, tmp_path):
        from src.execution_diagnosis import persist_diagnosis
        persist_diagnosis([self._artifact()], tmp_path)
        assert (tmp_path / "diagnosis.json").exists()

    def test_creates_output_dir_if_missing(self, tmp_path):
        from src.execution_diagnosis import persist_diagnosis
        new_dir = tmp_path / "nested" / "out"
        persist_diagnosis([self._artifact()], new_dir)
        assert (new_dir / "diagnosis.json").exists()

    def test_empty_list_writes_empty_array(self, tmp_path):
        import json
        from src.execution_diagnosis import persist_diagnosis
        persist_diagnosis([], tmp_path)
        data = json.loads((tmp_path / "diagnosis.json").read_text())
        assert data == []

    def test_written_json_is_list(self, tmp_path):
        import json
        from src.execution_diagnosis import persist_diagnosis
        persist_diagnosis([self._artifact()], tmp_path)
        data = json.loads((tmp_path / "diagnosis.json").read_text())
        assert isinstance(data, list)

    def test_written_entries_have_required_fields(self, tmp_path):
        import json
        from src.execution_diagnosis import persist_diagnosis
        persist_diagnosis([self._artifact()], tmp_path)
        data = json.loads((tmp_path / "diagnosis.json").read_text())
        assert len(data) == 1
        assert "diagnosis_type" in data[0]
        assert "summary" in data[0]
        assert "failures" in data[0]

    def test_returns_path_of_written_file(self, tmp_path):
        from src.execution_diagnosis import persist_diagnosis
        path = persist_diagnosis([self._artifact()], tmp_path)
        assert path == tmp_path / "diagnosis.json"
