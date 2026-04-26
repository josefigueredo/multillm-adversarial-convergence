"""Tests for MM10 Step 5 — Execution subsystem integration.

Covers:
- Adapter functions: build_implement_execution_plan, result_from_implement_state,
  build_research_execution_plan, result_from_findings
- diagnose_implement_failure: produces DiagnosisArtifact from failed TaskState
- diagnose_research_failure: produces DiagnosisArtifact for empty findings
- ImplementRunner wiring: diagnosis.json written on boundary violation, absent on success
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.execution_plan import ExecutionPlan, ExecutionStep, TargetContext
from src.execution_validator import ExecutionResult
from src.execution_diagnosis import DiagnosisArtifact


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _make_impl_config(tmp_path, task="Add retry logic", allowed_roots=(Path("src"),)):
    from src.implement_loop import ImplementConfig, ImplementTarget
    return ImplementConfig(
        target=ImplementTarget(path=tmp_path, allowed_roots=allowed_roots),
        task_description=task,
        max_cycles=2,
        convergence_cycles=1,
    )


def _make_task_state(*, violations=(), n_patches=0):
    from src.implement_loop import CandidatePatch, ImplementTask, TaskState
    state = TaskState(task=ImplementTask(description="test task"))
    for msg in violations:
        state.boundary_violations.append(msg)
    for i in range(n_patches):
        state.patches.append(CandidatePatch(content=f"patch-{i}", touched_files=(f"src/f{i}.py",)))
    return state


def _converging_strategy():
    from src.implement_loop import CandidatePatch
    strategy = MagicMock()
    strategy.run_builder.return_value = CandidatePatch(
        content="diff ...", touched_files=("src/main.py",)
    )
    strategy.run_challenger.return_value = []
    strategy.run_verifier.return_value = []
    return strategy


def _boundary_strategy():
    from src.implement_loop import CandidatePatch
    strategy = MagicMock()
    strategy.run_builder.return_value = CandidatePatch(
        content="bad", touched_files=("../evil.txt",)
    )
    return strategy


# ---------------------------------------------------------------------------
# TestBuildImplementExecutionPlan
# ---------------------------------------------------------------------------

class TestBuildImplementExecutionPlan:
    def test_returns_execution_plan(self, tmp_path):
        from src.execution_integration import build_implement_execution_plan
        plan = build_implement_execution_plan(_make_impl_config(tmp_path))
        assert isinstance(plan, ExecutionPlan)

    def test_has_one_step(self, tmp_path):
        from src.execution_integration import build_implement_execution_plan
        plan = build_implement_execution_plan(_make_impl_config(tmp_path))
        assert len(plan.steps) == 1

    def test_step_command_contains_task_description(self, tmp_path):
        from src.execution_integration import build_implement_execution_plan
        plan = build_implement_execution_plan(_make_impl_config(tmp_path, task="add auth"))
        assert "add auth" in plan.steps[0].command

    def test_target_working_dir_is_target_path(self, tmp_path):
        from src.execution_integration import build_implement_execution_plan
        plan = build_implement_execution_plan(_make_impl_config(tmp_path))
        assert plan.target.working_dir == tmp_path.resolve()


# ---------------------------------------------------------------------------
# TestResultFromImplementState
# ---------------------------------------------------------------------------

class TestResultFromImplementState:
    def test_no_violations_gives_exit_code_0(self, tmp_path):
        from src.execution_integration import result_from_implement_state
        state = _make_task_state()
        r = result_from_implement_state(state)
        assert r.exit_code == 0

    def test_boundary_violation_gives_exit_code_1(self, tmp_path):
        from src.execution_integration import result_from_implement_state
        state = _make_task_state(violations=["path escapes root"])
        r = result_from_implement_state(state)
        assert r.exit_code == 1

    def test_violations_appear_in_stderr(self, tmp_path):
        from src.execution_integration import result_from_implement_state
        state = _make_task_state(violations=["evil path detected"])
        r = result_from_implement_state(state)
        assert "evil path" in r.stderr

    def test_patch_count_in_stdout(self, tmp_path):
        from src.execution_integration import result_from_implement_state
        state = _make_task_state(n_patches=3)
        r = result_from_implement_state(state)
        assert "3" in r.stdout


# ---------------------------------------------------------------------------
# TestBuildResearchExecutionPlan
# ---------------------------------------------------------------------------

class TestBuildResearchExecutionPlan:
    def test_returns_execution_plan(self, tmp_path):
        from src.execution_integration import build_research_execution_plan
        plan = build_research_execution_plan("llm safety", ["q1"], tmp_path)
        assert isinstance(plan, ExecutionPlan)

    def test_step_includes_dimension(self, tmp_path):
        from src.execution_integration import build_research_execution_plan
        plan = build_research_execution_plan("llm safety", ["q1"], tmp_path)
        assert "llm safety" in plan.steps[0].command

    def test_one_step_for_any_question_count(self, tmp_path):
        from src.execution_integration import build_research_execution_plan
        plan = build_research_execution_plan("topic", [], tmp_path)
        assert len(plan.steps) == 1
        plan2 = build_research_execution_plan("topic", ["a", "b", "c"], tmp_path)
        assert len(plan2.steps) == 1

    def test_target_working_dir_matches(self, tmp_path):
        from src.execution_integration import build_research_execution_plan
        plan = build_research_execution_plan("topic", [], tmp_path)
        assert plan.target.working_dir == tmp_path.resolve()


# ---------------------------------------------------------------------------
# TestResultFromFindings
# ---------------------------------------------------------------------------

class TestResultFromFindings:
    def test_nonempty_findings_exit_code_0(self):
        from src.execution_integration import result_from_findings
        r = result_from_findings("some interesting finding")
        assert r.exit_code == 0

    def test_empty_findings_exit_code_1(self):
        from src.execution_integration import result_from_findings
        r = result_from_findings("")
        assert r.exit_code == 1

    def test_findings_appear_in_stdout(self):
        from src.execution_integration import result_from_findings
        r = result_from_findings("interesting finding")
        assert "interesting finding" in r.stdout

    def test_empty_findings_has_stderr_message(self):
        from src.execution_integration import result_from_findings
        r = result_from_findings("")
        assert r.stderr != ""


# ---------------------------------------------------------------------------
# TestDiagnoseImplementFailure
# ---------------------------------------------------------------------------

class TestDiagnoseImplementFailure:
    def test_boundary_violation_returns_artifacts(self, tmp_path):
        from src.execution_integration import diagnose_implement_failure
        state = _make_task_state(violations=["path escapes root"])
        config = _make_impl_config(tmp_path)
        artifacts = diagnose_implement_failure(state, config)
        assert len(artifacts) >= 1

    def test_artifacts_are_diagnosis_artifact_type(self, tmp_path):
        from src.execution_integration import diagnose_implement_failure
        state = _make_task_state(violations=["path escapes root"])
        config = _make_impl_config(tmp_path)
        artifacts = diagnose_implement_failure(state, config)
        assert all(isinstance(a, DiagnosisArtifact) for a in artifacts)

    def test_clean_state_returns_empty_list(self, tmp_path):
        from src.execution_integration import diagnose_implement_failure
        state = _make_task_state()
        config = _make_impl_config(tmp_path)
        artifacts = diagnose_implement_failure(state, config)
        assert artifacts == []


# ---------------------------------------------------------------------------
# TestDiagnoseResearchFailure
# ---------------------------------------------------------------------------

class TestDiagnoseResearchFailure:
    def test_returns_diagnosis_artifact(self, tmp_path):
        from src.execution_integration import diagnose_research_failure
        artifact = diagnose_research_failure("llm safety", tmp_path)
        assert isinstance(artifact, DiagnosisArtifact)

    def test_diagnosis_type_set(self, tmp_path):
        from src.execution_integration import diagnose_research_failure
        artifact = diagnose_research_failure("topic", tmp_path)
        assert artifact.diagnosis_type in (
            "exit_code_mismatch", "pattern_missing", "multiple", "timeout"
        )

    def test_summary_mentions_dimension(self, tmp_path):
        from src.execution_integration import diagnose_research_failure
        artifact = diagnose_research_failure("security properties", tmp_path)
        assert "security properties" in artifact.summary or "security properties" in artifact.step_name


# ---------------------------------------------------------------------------
# TestImplementRunnerDiagnosisWiring
# ---------------------------------------------------------------------------

class TestImplementRunnerDiagnosisWiring:
    def test_boundary_violation_writes_diagnosis_json(self, tmp_path):
        import json
        from src.implement_runner import ImplementRunner
        cfg = _make_impl_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=_boundary_strategy())
        assert (tmp_path / "diagnosis.json").exists()

    def test_diagnosis_json_is_valid_json_with_type_field(self, tmp_path):
        import json
        from src.implement_runner import ImplementRunner
        cfg = _make_impl_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=_boundary_strategy())
        data = json.loads((tmp_path / "diagnosis.json").read_text())
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "diagnosis_type" in data[0]

    def test_clean_run_does_not_write_diagnosis_json(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = _make_impl_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=_converging_strategy())
        assert not (tmp_path / "diagnosis.json").exists()
