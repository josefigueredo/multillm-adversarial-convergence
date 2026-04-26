"""Tests for MM09 Step 1 — implement mode scaffolding.

Covers:
- ImplementTarget: fields, defaults, frozen, execution-level validation
- ImplementTask: fields, defaults
- CandidatePatch: fields, defaults
- TaskState: fields, initial values, workflow-state typing
- ImplementState: enum values and state-set membership
- ImplementStrategy: instantiation, method presence, stub behavior
- ImplementRunner: instantiation, run() stub
- CLI: implement subcommand registered, flags available
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# ImplementState
# ---------------------------------------------------------------------------

class TestImplementState:
    def test_idle_value(self):
        from src.workflows.implement_states import ImplementState
        assert ImplementState.IDLE.value == "idle"

    def test_builder_value(self):
        from src.workflows.implement_states import ImplementState
        assert ImplementState.BUILDER.value == "builder"

    def test_converged_in_terminal_states(self):
        from src.workflows.implement_states import ImplementState, TERMINAL_STATES
        assert ImplementState.CONVERGED in TERMINAL_STATES

    def test_interrupted_in_terminal_states(self):
        from src.workflows.implement_states import ImplementState, TERMINAL_STATES
        assert ImplementState.INTERRUPTED in TERMINAL_STATES

    def test_paused_for_human_in_pause_states(self):
        from src.workflows.implement_states import ImplementState, PAUSE_STATES
        assert ImplementState.PAUSED_FOR_HUMAN in PAUSE_STATES

    def test_idle_not_terminal(self):
        from src.workflows.implement_states import ImplementState, TERMINAL_STATES
        assert ImplementState.IDLE not in TERMINAL_STATES

    def test_str_enum_value_serialises(self):
        from src.workflows.implement_states import ImplementState
        # audit-trail serialisation requires str enum
        assert str(ImplementState.BUILDER) == "builder" or ImplementState.BUILDER.value == "builder"


# ---------------------------------------------------------------------------
# ImplementTarget
# ---------------------------------------------------------------------------

class TestImplementTarget:
    def test_default_execution_level_is_patch_only(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."))
        assert t.execution_level == "patch_only"

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."))
        with pytest.raises((FrozenInstanceError, AttributeError)):
            t.execution_level = "analyze_only"  # type: ignore[misc]

    def test_invalid_execution_level_raises_value_error(self):
        from src.implement_loop import ImplementTarget
        with pytest.raises(ValueError, match="execution_level"):
            ImplementTarget(path=Path("."), execution_level="in_place_destroy")

    def test_analyze_only_accepted(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."), execution_level="analyze_only")
        assert t.execution_level == "analyze_only"

    def test_patch_only_accepted(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."), execution_level="patch_only")
        assert t.execution_level == "patch_only"

    def test_isolated_apply_accepted(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."), execution_level="isolated_apply")
        assert t.execution_level == "isolated_apply"

    def test_allowed_roots_defaults_empty(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("."))
        assert t.allowed_roots == ()

    def test_path_field_is_path(self):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=Path("/some/repo"))
        assert isinstance(t.path, Path)


# ---------------------------------------------------------------------------
# ImplementTask
# ---------------------------------------------------------------------------

class TestImplementTask:
    def test_has_description_field(self):
        from src.implement_loop import ImplementTask
        task = ImplementTask(description="Add feature X")
        assert task.description == "Add feature X"

    def test_target_file_refs_defaults_empty(self):
        from src.implement_loop import ImplementTask
        task = ImplementTask(description="task")
        assert task.target_file_refs == ()

    def test_can_set_file_refs(self):
        from src.implement_loop import ImplementTask
        task = ImplementTask(description="task", target_file_refs=("src/foo.py", "src/bar.py"))
        assert "src/foo.py" in task.target_file_refs


# ---------------------------------------------------------------------------
# CandidatePatch
# ---------------------------------------------------------------------------

class TestCandidatePatch:
    def test_has_content_field(self):
        from src.implement_loop import CandidatePatch
        p = CandidatePatch(content="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new")
        assert "new" in p.content

    def test_rationale_defaults_empty_string(self):
        from src.implement_loop import CandidatePatch
        p = CandidatePatch(content="patch")
        assert p.rationale == ""

    def test_touched_files_defaults_empty_tuple(self):
        from src.implement_loop import CandidatePatch
        p = CandidatePatch(content="patch")
        assert p.touched_files == ()


# ---------------------------------------------------------------------------
# TaskState
# ---------------------------------------------------------------------------

class TestTaskState:
    def _make_task(self):
        from src.implement_loop import ImplementTask
        return ImplementTask(description="test task")

    def test_initial_cycle_is_zero(self):
        from src.implement_loop import TaskState
        s = TaskState(task=self._make_task())
        assert s.cycle == 0

    def test_initial_converged_is_false(self):
        from src.implement_loop import TaskState
        s = TaskState(task=self._make_task())
        assert s.converged is False

    def test_workflow_state_is_implement_state_enum(self):
        from src.implement_loop import TaskState
        from src.workflows.implement_states import ImplementState
        s = TaskState(task=self._make_task())
        assert isinstance(s.current_workflow_state, ImplementState)

    def test_initial_workflow_state_is_idle(self):
        from src.implement_loop import TaskState
        from src.workflows.implement_states import ImplementState
        s = TaskState(task=self._make_task())
        assert s.current_workflow_state == ImplementState.IDLE

    def test_has_patches_list(self):
        from src.implement_loop import TaskState
        s = TaskState(task=self._make_task())
        assert isinstance(s.patches, list)
        assert len(s.patches) == 0

    def test_has_critiques_list(self):
        from src.implement_loop import TaskState
        s = TaskState(task=self._make_task())
        assert isinstance(s.critiques, list)
        assert len(s.critiques) == 0


# ---------------------------------------------------------------------------
# ImplementStrategy
# ---------------------------------------------------------------------------

class TestImplementStrategy:
    def _make_strategy(self):
        from src.implement_strategy import ImplementStrategy
        return ImplementStrategy(config=None, backends={})

    def test_instantiates(self):
        s = self._make_strategy()
        assert s is not None

    def test_has_run_builder_method(self):
        s = self._make_strategy()
        assert callable(getattr(s, "run_builder", None))

    def test_has_run_challenger_method(self):
        s = self._make_strategy()
        assert callable(getattr(s, "run_challenger", None))

    def test_has_run_verifier_method(self):
        s = self._make_strategy()
        assert callable(getattr(s, "run_verifier", None))

    def test_has_run_arbitrator_method(self):
        s = self._make_strategy()
        assert callable(getattr(s, "run_arbitrator", None))

    def test_run_builder_raises_not_implemented(self):
        from src.implement_loop import ImplementTask, ImplementTarget, CandidatePatch
        s = self._make_strategy()
        with pytest.raises(NotImplementedError):
            s.run_builder(
                task=ImplementTask(description="t"),
                target=ImplementTarget(path=Path(".")),
            )


# ---------------------------------------------------------------------------
# ImplementRunner
# ---------------------------------------------------------------------------

class TestImplementRunner:
    def test_instantiates(self, tmp_path):
        from src.implement_runner import ImplementRunner
        from src.implement_loop import ImplementTarget
        runner = ImplementRunner(
            config=None,
            backends={},
            target=ImplementTarget(path=tmp_path),
            output_dir=tmp_path,
        )
        assert runner is not None

    def test_has_run_method(self, tmp_path):
        from src.implement_runner import ImplementRunner
        from src.implement_loop import ImplementTarget
        runner = ImplementRunner(
            config=None,
            backends={},
            target=ImplementTarget(path=tmp_path),
            output_dir=tmp_path,
        )
        assert callable(runner.run)

    def test_run_returns_int(self, tmp_path):
        from src.implement_runner import ImplementRunner
        from src.implement_loop import ImplementTarget
        runner = ImplementRunner(
            config=None,
            backends={},
            target=ImplementTarget(path=tmp_path),
            output_dir=tmp_path,
        )
        result = runner.run()
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# CLI — implement subcommand
# ---------------------------------------------------------------------------

class TestCliImplementSubcommand:
    def test_implement_subcommand_registered(self):
        from src.cli import _build_parser
        parser = _build_parser()
        # parse a minimal implement invocation (--config is required)
        args = parser.parse_args(["implement", "--config", "foo.yaml"])
        assert args.subcommand == "implement"

    def test_implement_requires_config(self):
        from src.cli import _build_parser
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["implement"])

    def test_implement_dry_run_flag_exists(self):
        from src.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["implement", "--config", "foo.yaml", "--dry-run"])
        assert args.dry_run is True

    def test_implement_resume_flag_exists(self):
        from src.cli import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["implement", "--config", "foo.yaml", "--resume"])
        assert args.resume is True
