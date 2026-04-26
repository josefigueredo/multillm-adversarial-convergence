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
from unittest.mock import MagicMock, patch

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

    def test_run_builder_raises_runtime_error_when_backends_empty(self):
        from src.implement_loop import ImplementTask, ImplementTarget
        s = self._make_strategy()
        with pytest.raises(RuntimeError, match="backend"):
            s.run_builder(
                task=ImplementTask(description="t"),
                target=ImplementTarget(path=Path(".")),
                invoke=lambda *a, **kw: None,
            )


# ---------------------------------------------------------------------------
# ImplementRunner
# ---------------------------------------------------------------------------

class TestImplementRunner:
    def test_instantiates(self, tmp_path):
        from src.implement_runner import ImplementRunner
        runner = ImplementRunner(
            config=None,
            backends={},
            output_dir=tmp_path,
        )
        assert runner is not None

    def test_has_run_method(self, tmp_path):
        from src.implement_runner import ImplementRunner
        runner = ImplementRunner(
            config=None,
            backends={},
            output_dir=tmp_path,
        )
        assert callable(runner.run)

    def test_run_returns_int(self, tmp_path):
        from src.implement_runner import ImplementRunner
        runner = ImplementRunner(
            config=None,
            backends={},
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

    @patch("src.cli.get_backends")
    @patch("src.implement_runner.ImplementRunner.run")
    def test_non_dry_run_with_valid_config_proceeds(
        self, mock_run, mock_get_backends, tmp_path, capsys
    ):
        """Non-dry-run implement with a valid config and an available backend runs the loop."""
        from src.cli import _run_implement
        import argparse, logging

        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_run.return_value = 0

        config_file = tmp_path / "impl.yaml"
        config_file.write_text(f"target:\n  path: {tmp_path}\n")

        args = argparse.Namespace(
            config=config_file,
            output=tmp_path / "out",
            resume=False,
            dry_run=False,
        )
        rc = _run_implement(args, logging.getLogger("test"))
        assert rc == 0  # runner ran successfully
        mock_run.assert_called_once()

    def test_non_dry_run_with_missing_target_path_returns_1(self, tmp_path, capsys):
        """Non-dry-run with a config that omits target.path must fail with rc == 1."""
        from src.cli import _run_implement
        import argparse, logging

        config_file = tmp_path / "impl.yaml"
        config_file.write_text("target:\n  execution_level: patch_only\n")

        args = argparse.Namespace(
            config=config_file,
            output=None,
            resume=False,
            dry_run=False,
        )
        rc = _run_implement(args, logging.getLogger("test"))
        assert rc == 1

    def test_dry_run_shows_resolved_target_from_config(self, tmp_path, capsys):
        """dry-run must show the config-derived target path, not a fabricated default."""
        from src.cli import _run_implement
        import argparse, logging

        target_dir = tmp_path / "my_repo"
        target_dir.mkdir()
        config_file = tmp_path / "impl.yaml"
        config_file.write_text(f"target:\n  path: {target_dir}\n")

        args = argparse.Namespace(
            config=config_file,
            output=None,
            resume=False,
            dry_run=True,
        )
        rc = _run_implement(args, logging.getLogger("test"))
        out = capsys.readouterr().out
        assert rc == 0
        assert str(target_dir) in out, "dry-run must show the config-derived target path"
        assert "deferred" not in out, "Step 2 dry-run must not say 'deferred' — target is now real"


# ---------------------------------------------------------------------------
# ImplementConfig
# ---------------------------------------------------------------------------

class TestImplementConfig:
    def _yaml(self, tmp_path, content: str):
        f = tmp_path / "impl.yaml"
        f.write_text(content)
        return f

    def test_from_yaml_minimal(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n")
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.target.path == tmp_path.resolve()
        assert cfg.target.execution_level == "patch_only"
        assert cfg.target.allowed_roots == ()

    def test_from_yaml_with_execution_level(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n  execution_level: analyze_only\n")
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.target.execution_level == "analyze_only"

    def test_from_yaml_with_allowed_roots(self, tmp_path):
        from src.implement_loop import ImplementConfig
        from pathlib import Path
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n  allowed_roots:\n    - src\n    - tests\n")
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.target.allowed_roots == (Path("src"), Path("tests"))

    def test_defaults_execution_level_to_patch_only(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n")
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.target.execution_level == "patch_only"

    def test_missing_target_path_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, "target:\n  execution_level: patch_only\n")
        with pytest.raises(ValueError, match="target.path"):
            ImplementConfig.from_yaml(cfg_file)

    def test_missing_target_section_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, "execution_level: patch_only\n")
        with pytest.raises(ValueError, match="target"):
            ImplementConfig.from_yaml(cfg_file)

    def test_invalid_execution_level_raises_via_target(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n  execution_level: destroy_everything\n")
        with pytest.raises(ValueError, match="execution_level"):
            ImplementConfig.from_yaml(cfg_file)

    def test_non_mapping_yaml_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, "- just\n- a\n- list\n")
        with pytest.raises(ValueError):
            ImplementConfig.from_yaml(cfg_file)

    def test_non_mapping_target_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, "target: just_a_string\n")
        with pytest.raises(ValueError, match="target"):
            ImplementConfig.from_yaml(cfg_file)

    def test_allowed_roots_as_string_raises(self, tmp_path):
        """allowed_roots must be a list, not a bare string."""
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n  allowed_roots: src\n")
        with pytest.raises(ValueError, match="allowed_roots"):
            ImplementConfig.from_yaml(cfg_file)

    def test_relative_target_path_resolved_against_config_dir(self, tmp_path):
        """A relative target.path must be resolved against the config file's directory."""
        from src.implement_loop import ImplementConfig
        sub = tmp_path / "repo"
        sub.mkdir()
        cfg_file = self._yaml(tmp_path, "target:\n  path: repo\n")
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.target.path == sub.resolve()

    def test_file_not_found_raises_oserror(self, tmp_path):
        from src.implement_loop import ImplementConfig
        with pytest.raises(OSError):
            ImplementConfig.from_yaml(tmp_path / "nonexistent.yaml")

    def test_nonexistent_target_path_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg_file = self._yaml(tmp_path, "target:\n  path: /this/does/not/exist/ever\n")
        with pytest.raises(ValueError, match="not exist"):
            ImplementConfig.from_yaml(cfg_file)

    def test_file_path_as_target_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementConfig
        a_file = tmp_path / "somefile.txt"
        a_file.write_text("hello")
        cfg_file = self._yaml(tmp_path, f"target:\n  path: {a_file}\n")
        with pytest.raises(ValueError, match="directory"):
            ImplementConfig.from_yaml(cfg_file)


# ---------------------------------------------------------------------------
# ImplementTarget — allowed_roots contract
# ---------------------------------------------------------------------------

class TestImplementTargetAllowedRoots:
    def test_empty_allowed_roots_accepted(self, tmp_path):
        from src.implement_loop import ImplementTarget
        t = ImplementTarget(path=tmp_path, allowed_roots=())
        assert t.allowed_roots == ()

    def test_relative_allowed_roots_accepted(self, tmp_path):
        from src.implement_loop import ImplementTarget
        from pathlib import Path
        t = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"), Path("tests")))
        assert len(t.allowed_roots) == 2

    def test_absolute_allowed_root_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementTarget
        from pathlib import Path
        with pytest.raises(ValueError, match="absolute"):
            ImplementTarget(path=tmp_path, allowed_roots=(Path("/etc/passwd"),))

    def test_traversal_in_allowed_root_raises_value_error(self, tmp_path):
        from src.implement_loop import ImplementTarget
        from pathlib import Path
        with pytest.raises(ValueError, match="traversal"):
            ImplementTarget(path=tmp_path, allowed_roots=(Path("../outside"),))


# ---------------------------------------------------------------------------
# Step 3 — Adversarial workflow data types
# ---------------------------------------------------------------------------

class TestImplementCritique:
    def test_has_description(self):
        from src.implement_loop import ImplementCritique
        c = ImplementCritique(description="Missing null check", file_ref="src/foo.py", raised_by="challenger")
        assert c.description == "Missing null check"

    def test_has_file_ref(self):
        from src.implement_loop import ImplementCritique
        c = ImplementCritique(description="d", file_ref="src/foo.py", raised_by="challenger")
        assert c.file_ref == "src/foo.py"

    def test_has_raised_by(self):
        from src.implement_loop import ImplementCritique
        c = ImplementCritique(description="d", file_ref="f", raised_by="challenger")
        assert c.raised_by == "challenger"


class TestVerifiedImplementCritique:
    def test_has_status_field(self):
        from src.implement_loop import VerifiedImplementCritique
        v = VerifiedImplementCritique(
            description="Missing check", file_ref="src/a.py",
            raised_by="challenger", status="valid",
        )
        assert v.status == "valid"

    def test_stale_status_accepted(self):
        from src.implement_loop import VerifiedImplementCritique
        v = VerifiedImplementCritique(description="d", file_ref="f", raised_by="r", status="stale")
        assert v.status == "stale"

    def test_all_fields_present(self):
        from src.implement_loop import VerifiedImplementCritique
        v = VerifiedImplementCritique(
            description="d", file_ref="f", raised_by="r", status="valid"
        )
        assert v.description == "d"
        assert v.file_ref == "f"
        assert v.raised_by == "r"


class TestTaskStateNewFields:
    def _make_state(self):
        from src.implement_loop import TaskState, ImplementTask
        return TaskState(task=ImplementTask(description="task"))

    def test_consecutive_clean_cycles_defaults_zero(self):
        state = self._make_state()
        assert state.consecutive_clean_cycles == 0

    def test_pending_critiques_defaults_empty(self):
        state = self._make_state()
        assert state.pending_critiques == []

    def test_critiques_is_list(self):
        state = self._make_state()
        assert isinstance(state.critiques, list)


# ---------------------------------------------------------------------------
# Step 3 — ImplementConfig new fields
# ---------------------------------------------------------------------------

class TestImplementConfigCycleFields:
    def _yaml(self, tmp_path, content):
        f = tmp_path / "impl.yaml"
        f.write_text(content)
        return f

    def test_defaults_max_cycles_to_5(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n"))
        assert cfg.max_cycles == 5

    def test_defaults_convergence_cycles_to_1(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n"))
        assert cfg.convergence_cycles == 1

    def test_defaults_task_description_to_empty(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(tmp_path, f"target:\n  path: {tmp_path}\n"))
        assert cfg.task_description == ""

    def test_parses_max_cycles(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(tmp_path, f"max_cycles: 3\ntarget:\n  path: {tmp_path}\n"))
        assert cfg.max_cycles == 3

    def test_parses_convergence_cycles(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(tmp_path, f"convergence_cycles: 2\ntarget:\n  path: {tmp_path}\n"))
        assert cfg.convergence_cycles == 2

    def test_parses_task_description(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._yaml(
            tmp_path, f"task_description: 'Add type hints'\ntarget:\n  path: {tmp_path}\n"
        ))
        assert cfg.task_description == "Add type hints"

    def test_convergence_cycles_zero_raises(self, tmp_path):
        from src.implement_loop import ImplementConfig
        with pytest.raises(ValueError, match="convergence_cycles"):
            ImplementConfig.from_yaml(self._yaml(
                tmp_path, f"convergence_cycles: 0\ntarget:\n  path: {tmp_path}\n"
            ))


# ---------------------------------------------------------------------------
# Step 3 — Convergence helpers
# ---------------------------------------------------------------------------

class TestShouldStopImplement:
    def _make_config(self, tmp_path, max_cycles=5, convergence_cycles=1):
        from src.implement_loop import ImplementConfig
        f = tmp_path / "i.yaml"
        f.write_text(
            f"max_cycles: {max_cycles}\nconvergence_cycles: {convergence_cycles}\n"
            f"target:\n  path: {tmp_path}\n"
        )
        return ImplementConfig.from_yaml(f)

    def _make_state(self):
        from src.implement_loop import TaskState, ImplementTask
        return TaskState(task=ImplementTask(description="t"))

    def test_stops_when_clean_cycles_reached(self, tmp_path):
        from src.implement_loop import _should_stop_implement
        cfg = self._make_config(tmp_path, convergence_cycles=1)
        state = self._make_state()
        state.consecutive_clean_cycles = 1
        assert _should_stop_implement(state, cfg) is True

    def test_continues_when_no_clean_cycles(self, tmp_path):
        from src.implement_loop import _should_stop_implement
        cfg = self._make_config(tmp_path, convergence_cycles=1)
        state = self._make_state()
        state.consecutive_clean_cycles = 0
        assert _should_stop_implement(state, cfg) is False

    def test_stops_when_max_cycles_reached(self, tmp_path):
        from src.implement_loop import _should_stop_implement
        cfg = self._make_config(tmp_path, max_cycles=3, convergence_cycles=99)
        state = self._make_state()
        state.cycle = 3
        assert _should_stop_implement(state, cfg) is True

    def test_continues_when_below_max_cycles(self, tmp_path):
        from src.implement_loop import _should_stop_implement
        cfg = self._make_config(tmp_path, max_cycles=5, convergence_cycles=99)
        state = self._make_state()
        state.cycle = 2
        assert _should_stop_implement(state, cfg) is False

    def test_max_cycles_zero_never_stops_on_cycles(self, tmp_path):
        from src.implement_loop import _should_stop_implement
        cfg = self._make_config(tmp_path, max_cycles=0, convergence_cycles=1)
        state = self._make_state()
        state.cycle = 100  # does not trigger max_cycles check
        state.consecutive_clean_cycles = 0
        assert _should_stop_implement(state, cfg) is False


# ---------------------------------------------------------------------------
# Step 3 — run_implement_cycle
# ---------------------------------------------------------------------------

class TestRunImplementCycle:
    """Tests for run_implement_cycle() control flow using mock strategy."""

    def _make_ctx(self, tmp_path):
        from src.implement_loop import ImplementCycleContext, ImplementTarget
        from src.audit_trail import NullAuditTrailWriter
        target = ImplementTarget(path=tmp_path)
        noop = lambda *a, **kw: None
        return ImplementCycleContext(
            call_with=noop,
            invoke_for_strategy=noop,
            track_usage=noop,
            track_cost=noop,
            target=target,
            audit_trail=NullAuditTrailWriter(),
        )

    def _make_state(self, task_description="implement feature X"):
        from src.implement_loop import TaskState, ImplementTask
        return TaskState(task=ImplementTask(description=task_description))

    def _clean_strategy(self, tmp_path):
        """Strategy that returns a patch and zero valid critiques (converges)."""
        from unittest.mock import MagicMock
        from src.implement_loop import CandidatePatch, VerifiedImplementCritique
        strategy = MagicMock()
        strategy.run_builder.return_value = CandidatePatch(content="diff --git ...")
        strategy.run_challenger.return_value = []
        strategy.run_verifier.return_value = []
        return strategy

    def _dirty_strategy(self, tmp_path):
        """Strategy with one valid critique — arbitrator returns revised patch."""
        from unittest.mock import MagicMock
        from src.implement_loop import CandidatePatch, ImplementCritique, VerifiedImplementCritique
        strategy = MagicMock()
        strategy.run_builder.return_value = CandidatePatch(content="initial patch")
        strategy.run_challenger.return_value = [
            ImplementCritique(description="Missing null check", file_ref="src/a.py", raised_by="challenger")
        ]
        strategy.run_verifier.return_value = [
            VerifiedImplementCritique(description="Missing null check", file_ref="src/a.py", raised_by="challenger", status="valid")
        ]
        strategy.run_arbitrator.return_value = CandidatePatch(content="revised patch")
        return strategy

    def test_cycle_increments(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert state.cycle == 1

    def test_builder_called_with_task_and_target(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        strategy.run_builder.assert_called_once()
        call_kwargs = strategy.run_builder.call_args
        assert call_kwargs is not None

    def test_builder_patch_added_to_history(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert len(state.patches) >= 1

    def test_challenger_called_with_patch(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        strategy.run_challenger.assert_called_once()

    def test_verifier_called(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        strategy.run_verifier.assert_called_once()

    def test_arbitrator_not_called_when_no_valid_critiques(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        strategy.run_arbitrator.assert_not_called()

    def test_clean_cycle_increments_consecutive_clean(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._clean_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert state.consecutive_clean_cycles == 1

    def test_dirty_cycle_resets_consecutive_clean(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        state.consecutive_clean_cycles = 2  # simulated prior clean run
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert state.consecutive_clean_cycles == 0

    def test_dirty_cycle_calls_arbitrator(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        strategy.run_arbitrator.assert_called_once()

    def test_dirty_cycle_appends_revised_patch(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        # builder patch + arbitrator revised patch
        assert len(state.patches) == 2
        assert state.patches[-1].content == "revised patch"

    def test_valid_critiques_stored_in_pending_for_next_cycle(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert len(state.pending_critiques) == 1
        assert state.pending_critiques[0].status == "valid"

    def test_critiques_accumulated_in_history(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        run_implement_cycle(state, ctx, strategy)
        assert len(state.critiques) == 1

    def test_returns_valid_stale_deferred_counts(self, tmp_path):
        from src.implement_loop import run_implement_cycle
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        valid, stale, deferred = run_implement_cycle(state, ctx, strategy)
        assert valid == 1
        assert stale == 0
        assert deferred == 0

    def test_builder_receives_previous_patch_on_second_cycle(self, tmp_path):
        from src.implement_loop import run_implement_cycle, CandidatePatch
        state = self._make_state()
        ctx = self._make_ctx(tmp_path)
        strategy = self._dirty_strategy(tmp_path)
        # First cycle produces a revised patch and pending critiques
        run_implement_cycle(state, ctx, strategy)
        # Second cycle: configure strategy to return clean result
        strategy.run_verifier.return_value = []
        strategy.run_challenger.return_value = []
        run_implement_cycle(state, ctx, strategy)
        # Builder should have been called twice
        assert strategy.run_builder.call_count == 2
        # Second call's last_patch kwarg should be the revised patch from cycle 1
        _, kwargs2 = strategy.run_builder.call_args_list[1]
        assert kwargs2.get("last_patch") is not None


# ---------------------------------------------------------------------------
# Step 3 — ImplementRunner loop
# ---------------------------------------------------------------------------

class TestImplementRunnerLoop:
    def _make_config(self, tmp_path, max_cycles=3, convergence_cycles=1, task_description="implement X"):
        from src.implement_loop import ImplementConfig
        f = tmp_path / "impl.yaml"
        f.write_text(
            f"task_description: '{task_description}'\n"
            f"max_cycles: {max_cycles}\n"
            f"convergence_cycles: {convergence_cycles}\n"
            f"target:\n  path: {tmp_path}\n"
        )
        return ImplementConfig.from_yaml(f)

    def _clean_strategy(self):
        from unittest.mock import MagicMock
        from src.implement_loop import CandidatePatch
        s = MagicMock()
        s.run_builder.return_value = CandidatePatch(content="patch")
        s.run_challenger.return_value = []
        s.run_verifier.return_value = []
        return s

    def _always_dirty_strategy(self):
        from unittest.mock import MagicMock
        from src.implement_loop import CandidatePatch, ImplementCritique, VerifiedImplementCritique
        s = MagicMock()
        s.run_builder.return_value = CandidatePatch(content="patch")
        s.run_challenger.return_value = [
            ImplementCritique(description="issue", file_ref="f", raised_by="challenger")
        ]
        s.run_verifier.return_value = [
            VerifiedImplementCritique(description="issue", file_ref="f", raised_by="challenger", status="valid")
        ]
        s.run_arbitrator.return_value = CandidatePatch(content="revised")
        return s

    def test_no_backends_returns_1(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run()
        assert rc == 1

    def test_converges_in_one_clean_cycle(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, convergence_cycles=1)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run(_strategy=self._clean_strategy())
        assert rc == 0

    def test_converged_flag_set_on_true_convergence(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, convergence_cycles=1)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._clean_strategy())
        assert runner.state.converged is True

    def test_stops_at_max_cycles(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, max_cycles=2, convergence_cycles=99)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run(_strategy=self._always_dirty_strategy())
        assert rc == 0
        assert runner.state.cycle == 2

    def test_converged_false_on_max_cycles_stop(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, max_cycles=2, convergence_cycles=99)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._always_dirty_strategy())
        assert runner.state.converged is False

    def test_patches_produced(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, convergence_cycles=1)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._clean_strategy())
        assert len(runner.state.patches) >= 1


# ---------------------------------------------------------------------------
# Step 3 — ImplementStrategy method signatures
# ---------------------------------------------------------------------------

class TestImplementStrategySignatures:
    def test_run_builder_accepts_invoke_kwarg(self, tmp_path):
        from src.implement_strategy import ImplementStrategy
        from src.implement_loop import ImplementTask, ImplementTarget
        import inspect
        sig = inspect.signature(ImplementStrategy.run_builder)
        assert "invoke" in sig.parameters

    def test_run_challenger_accepts_invoke_kwarg(self):
        from src.implement_strategy import ImplementStrategy
        import inspect
        sig = inspect.signature(ImplementStrategy.run_challenger)
        assert "invoke" in sig.parameters

    def test_run_verifier_accepts_task_and_target(self):
        from src.implement_strategy import ImplementStrategy
        import inspect
        sig = inspect.signature(ImplementStrategy.run_verifier)
        assert "task" in sig.parameters
        assert "target" in sig.parameters

    def test_run_arbitrator_accepts_invoke_kwarg(self):
        from src.implement_strategy import ImplementStrategy
        import inspect
        sig = inspect.signature(ImplementStrategy.run_arbitrator)
        assert "invoke" in sig.parameters


# ---------------------------------------------------------------------------
# Step 3 refinement — ImplementConfig backends / providers contract
# ---------------------------------------------------------------------------

class TestImplementConfigBackendsContract:
    """ImplementConfig must parse and expose a backends/providers section."""

    def _make_config_file(self, tmp_path, extra_yaml: str = "") -> object:
        target = tmp_path / "repo"
        target.mkdir()
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(f"target:\n  path: {target}\n{extra_yaml}")
        return cfg_file

    def test_default_backends_is_BackendsConfig(self, tmp_path):
        from src.implement_loop import ImplementConfig, ImplementTarget
        from src.config import BackendsConfig
        cfg = ImplementConfig(target=ImplementTarget(path=tmp_path))
        assert isinstance(cfg.backends, BackendsConfig)

    def test_default_providers_is_empty_dict(self, tmp_path):
        from src.implement_loop import ImplementConfig, ImplementTarget
        cfg = ImplementConfig(target=ImplementTarget(path=tmp_path))
        assert cfg.providers == {}

    def test_from_yaml_default_backends_primary_is_claude_cli(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._make_config_file(tmp_path))
        assert cfg.backends.primary == "claude-cli"

    def test_from_yaml_parses_backends_primary(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._make_config_file(
            tmp_path,
            "backends:\n  primary: claude-cli\n",
        ))
        assert cfg.backends.primary == "claude-cli"

    def test_from_yaml_parses_multiple_backend_names(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._make_config_file(
            tmp_path,
            "backends:\n  primary: claude-cli\n  judge: gemini-cli\n",
        ))
        assert cfg.backends.primary == "claude-cli"
        assert cfg.backends.judge == "gemini-cli"

    def test_all_backend_names_returns_set(self, tmp_path):
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(self._make_config_file(tmp_path))
        names = cfg.backends.all_backend_names()
        assert isinstance(names, (set, frozenset))
        assert "claude-cli" in names


# ---------------------------------------------------------------------------
# Step 3 refinement — CLI backend wiring for implement
# ---------------------------------------------------------------------------

class TestCliImplementBackendWiring:
    """_run_implement() must load and pass real backends, not always {}."""

    def _make_args(self, config_file, dry_run=False, output=None, resume=False):
        import argparse
        return argparse.Namespace(
            config=config_file,
            output=output,
            resume=resume,
            dry_run=dry_run,
        )

    def _make_config_file(self, tmp_path, extra_yaml: str = "") -> object:
        target = tmp_path / "repo"
        target.mkdir()
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(f"target:\n  path: {target}\n{extra_yaml}")
        return cfg_file

    @patch("src.cli.get_backends")
    @patch("src.implement_runner.ImplementRunner.run")
    def test_valid_config_with_available_backend_reaches_runner(
        self, mock_run, mock_get_backends, tmp_path
    ):
        """With a working backend the runner is called and its exit code returned."""
        import logging
        from src.cli import _run_implement

        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_run.return_value = 0

        cfg_file = self._make_config_file(tmp_path)
        rc = _run_implement(self._make_args(cfg_file), logging.getLogger("test"))

        assert rc == 0
        mock_run.assert_called_once()

    @patch("src.cli.get_backends")
    def test_unavailable_backend_returns_1(self, mock_get_backends, tmp_path):
        """Unavailable backend must return rc=1 before reaching the runner."""
        import logging
        from src.cli import _run_implement

        mock_backend = MagicMock()
        mock_backend.check_available.return_value = False
        mock_backend.cli_executable.return_value = "claude"
        mock_backend.name = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_backend}

        cfg_file = self._make_config_file(tmp_path)
        rc = _run_implement(self._make_args(cfg_file), logging.getLogger("test"))

        assert rc == 1

    @patch("src.cli.get_backends")
    @patch("src.implement_runner.ImplementRunner.run")
    def test_runner_receives_non_empty_backends(
        self, mock_run, mock_get_backends, tmp_path
    ):
        """ImplementRunner must be constructed with the resolved backends dict."""
        import logging
        from src.cli import _run_implement

        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_run.return_value = 0

        cfg_file = self._make_config_file(tmp_path)

        with patch("src.implement_runner.ImplementRunner.__init__", return_value=None) as mock_init:
            _run_implement(self._make_args(cfg_file), logging.getLogger("test"))

        call_kwargs = mock_init.call_args.kwargs
        assert call_kwargs["backends"] != {}
        assert "claude-cli" in call_kwargs["backends"]


# ---------------------------------------------------------------------------
# Step 3 refinement — provider-instance backend contract
# ---------------------------------------------------------------------------

class TestImplementConfigProviderBranch:
    """ImplementConfig.from_yaml() must handle provider-instance names correctly.

    When providers are declared, backends section uses instance names
    (e.g. 'primary_reasoner'), NOT adapter names (e.g. 'claude-cli').
    These must not be routed through _parse_backends_config which validates
    against VALID_BACKENDS.
    """

    def _write_config(self, tmp_path, yaml_content: str):
        target = tmp_path / "repo"
        target.mkdir(exist_ok=True)
        cfg = tmp_path / "impl.yaml"
        cfg.write_text(f"target:\n  path: {target}\n" + yaml_content)
        return cfg

    def test_provider_backed_config_loads_successfully(self, tmp_path):
        """Provider instance names must not be rejected as invalid backend adapters."""
        from src.implement_loop import ImplementConfig
        yaml_extra = (
            "providers:\n"
            "  primary_reasoner:\n"
            "    adapter: claude-cli\n"
            "backends:\n"
            "  primary: primary_reasoner\n"
        )
        cfg = ImplementConfig.from_yaml(self._write_config(tmp_path, yaml_extra))
        assert cfg.backends.primary == "primary_reasoner"
        assert cfg.providers["primary_reasoner"].adapter == "claude-cli"

    def test_provider_backed_config_no_explicit_backends_uses_first_provider(self, tmp_path):
        """When providers declared but no backends section, first provider becomes primary."""
        from src.implement_loop import ImplementConfig
        yaml_extra = (
            "providers:\n"
            "  fast_model:\n"
            "    adapter: claude-cli\n"
        )
        cfg = ImplementConfig.from_yaml(self._write_config(tmp_path, yaml_extra))
        assert cfg.backends.primary == "fast_model"

    def test_unknown_provider_reference_fails(self, tmp_path):
        """Backends referencing an undeclared provider instance must raise ValueError."""
        from src.implement_loop import ImplementConfig
        yaml_extra = (
            "providers:\n"
            "  known_instance:\n"
            "    adapter: claude-cli\n"
            "backends:\n"
            "  primary: unknown_instance\n"
        )
        with pytest.raises(ValueError):
            ImplementConfig.from_yaml(self._write_config(tmp_path, yaml_extra))

    def test_direct_backend_name_without_providers_still_works(self, tmp_path):
        """Without providers, adapter names like claude-cli must still be accepted."""
        from src.implement_loop import ImplementConfig
        yaml_extra = "backends:\n  primary: claude-cli\n"
        cfg = ImplementConfig.from_yaml(self._write_config(tmp_path, yaml_extra))
        assert cfg.backends.primary == "claude-cli"
        assert cfg.providers == {}

    def test_invalid_adapter_name_without_providers_fails(self, tmp_path):
        """Without providers, invalid adapter names must still be rejected."""
        from src.implement_loop import ImplementConfig
        yaml_extra = "backends:\n  primary: not-a-real-adapter\n"
        with pytest.raises(ValueError):
            ImplementConfig.from_yaml(self._write_config(tmp_path, yaml_extra))


# ===========================================================================
# MM09 Step 4 — Safety guardrails
# ===========================================================================

# ---------------------------------------------------------------------------
# Self-hosting safety gate
# ---------------------------------------------------------------------------

class TestSelfHostingGuard:
    """from_yaml() must reject same-repo targets unless allow_same_repo: true."""

    def _repo_root(self):
        import src.implement_loop as m
        return Path(m.__file__).parent.parent

    def test_same_repo_target_raises_without_flag(self, tmp_path):
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(f"target:\n  path: {self._repo_root()}\n")
        with pytest.raises(ValueError, match="[Ss]elf.hosting|[Ss]ame.repo|[Pp]lanner"):
            from src.implement_loop import ImplementConfig
            ImplementConfig.from_yaml(cfg_file)

    def test_same_repo_target_accepted_with_allow_flag(self, tmp_path):
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(
            f"target:\n  path: {self._repo_root()}\nallow_same_repo: true\n"
        )
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.allow_same_repo is True

    def test_different_repo_always_accepted(self, tmp_path):
        other = tmp_path / "other_repo"
        other.mkdir()
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(f"target:\n  path: {other}\n")
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.allow_same_repo is False

    def test_allow_same_repo_defaults_to_false(self, tmp_path):
        other = tmp_path / "repo"
        other.mkdir()
        cfg_file = tmp_path / "impl.yaml"
        cfg_file.write_text(f"target:\n  path: {other}\n")
        from src.implement_loop import ImplementConfig
        cfg = ImplementConfig.from_yaml(cfg_file)
        assert cfg.allow_same_repo is False


# ---------------------------------------------------------------------------
# Patch boundary validation
# ---------------------------------------------------------------------------

class TestValidatePatchBoundaries:
    """validate_patch_boundaries(patch, target) -> list[str]."""

    def test_no_allowed_roots_never_violates(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path)
        patch = CandidatePatch(content="x", touched_files=("src/main.py", "tests/foo.py"))
        assert validate_patch_boundaries(patch, target) == []

    def test_file_within_allowed_root_no_violation(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x", touched_files=("src/main.py",))
        assert validate_patch_boundaries(patch, target) == []

    def test_file_outside_allowed_root_is_violation(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x", touched_files=("tests/foo.py",))
        violations = validate_patch_boundaries(patch, target)
        assert len(violations) == 1
        assert "tests/foo.py" in violations[0]

    def test_absolute_path_in_touched_files_is_violation(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x", touched_files=("/etc/passwd",))
        violations = validate_patch_boundaries(patch, target)
        assert len(violations) == 1

    def test_empty_touched_files_no_violation(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x")
        assert validate_patch_boundaries(patch, target) == []

    def test_multiple_files_multiple_violations(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x", touched_files=("tests/a.py", "docs/b.md"))
        violations = validate_patch_boundaries(patch, target)
        assert len(violations) == 2

    def test_nested_file_within_root_no_violation(self, tmp_path):
        from src.implement_loop import ImplementTarget, CandidatePatch, validate_patch_boundaries
        target = ImplementTarget(path=tmp_path, allowed_roots=(Path("src"),))
        patch = CandidatePatch(content="x", touched_files=("src/utils/helpers.py",))
        assert validate_patch_boundaries(patch, target) == []


# ---------------------------------------------------------------------------
# TaskState boundary_violations field
# ---------------------------------------------------------------------------

class TestTaskStateBoundaryViolations:
    def test_boundary_violations_defaults_empty(self, tmp_path):
        from src.implement_loop import TaskState, ImplementTask
        state = TaskState(task=ImplementTask(description="t"))
        assert state.boundary_violations == []


# ---------------------------------------------------------------------------
# Boundary enforcement in cycle and runner
# ---------------------------------------------------------------------------

class TestBoundaryEnforcementInRunner:
    """Runner must exit 1 and stop when a patch violates allowed_roots."""

    def _make_config(self, tmp_path, allowed_roots=()):
        from src.implement_loop import ImplementConfig, ImplementTarget
        target = ImplementTarget(path=tmp_path, allowed_roots=allowed_roots)
        return ImplementConfig(
            target=target,
            task_description="test",
            max_cycles=5,
            convergence_cycles=1,
        )

    def _strategy_touching(self, files):
        """Mock strategy whose builder returns a patch touching specific files."""
        from src.implement_loop import CandidatePatch, VerifiedImplementCritique
        strategy = MagicMock()
        strategy.run_builder.return_value = CandidatePatch(
            content="diff", touched_files=tuple(files)
        )
        strategy.run_challenger.return_value = []
        strategy.run_verifier.return_value = []
        strategy.run_arbitrator.return_value = CandidatePatch(content="diff")
        return strategy

    def test_boundary_violation_makes_runner_return_1(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, allowed_roots=(Path("src"),))
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        # Patch touches a file outside allowed_roots
        rc = runner.run(_strategy=self._strategy_touching(["tests/outside.py"]))
        assert rc == 1

    def test_clean_patch_runner_returns_0(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, allowed_roots=(Path("src"),))
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run(_strategy=self._strategy_touching(["src/main.py"]))
        assert rc == 0

    def test_boundary_violation_stops_before_challenger(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, allowed_roots=(Path("src"),))
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        strat = self._strategy_touching(["tests/outside.py"])
        runner.run(_strategy=strat)
        strat.run_challenger.assert_not_called()

    def test_boundary_violations_stored_in_state(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path, allowed_roots=(Path("src"),))
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._strategy_touching(["tests/outside.py"]))
        assert len(runner.state.boundary_violations) >= 1

    def test_should_stop_on_boundary_violation(self, tmp_path):
        from src.implement_loop import _should_stop_implement, TaskState, ImplementTask, ImplementConfig, ImplementTarget
        cfg = ImplementConfig(
            target=ImplementTarget(path=tmp_path),
            max_cycles=10, convergence_cycles=3,
        )
        state = TaskState(task=ImplementTask(description="t"))
        assert not _should_stop_implement(state, cfg)
        state.boundary_violations.append("file outside allowed_roots: tests/x.py")
        assert _should_stop_implement(state, cfg)


# ---------------------------------------------------------------------------
# Step 4 refinement — arbitrator patch boundary enforcement
# ---------------------------------------------------------------------------

class TestArbitratorBoundaryEnforcement:
    """validate_patch_boundaries must also run on the arbitrator's revised patch."""

    def _make_config(self, tmp_path, allowed_roots=(Path("src"),)):
        from src.implement_loop import ImplementConfig, ImplementTarget
        return ImplementConfig(
            target=ImplementTarget(path=tmp_path, allowed_roots=allowed_roots),
            task_description="test",
            max_cycles=5,
            convergence_cycles=1,
        )

    def _strategy_builder_ok_arbitrator_bad(self, bad_files):
        """Builder patch is within bounds; arbitrator returns out-of-bounds patch."""
        from src.implement_loop import (
            CandidatePatch, ImplementCritique, VerifiedImplementCritique,
        )
        strategy = MagicMock()
        # Builder: touches a file inside allowed_roots
        strategy.run_builder.return_value = CandidatePatch(
            content="good", touched_files=("src/main.py",)
        )
        # Challenger: raises a critique
        strategy.run_challenger.return_value = [
            ImplementCritique(description="issue", file_ref="src/main.py", raised_by="challenger")
        ]
        # Verifier: marks critique as valid
        strategy.run_verifier.return_value = [
            VerifiedImplementCritique(
                description="issue", file_ref="src/main.py", raised_by="challenger", status="valid"
            )
        ]
        # Arbitrator: returns a patch touching files outside allowed_roots
        strategy.run_arbitrator.return_value = CandidatePatch(
            content="revised", touched_files=tuple(bad_files)
        )
        return strategy

    def test_arbitrator_out_of_bounds_patch_makes_runner_return_1(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run(_strategy=self._strategy_builder_ok_arbitrator_bad(["docs/outside.md"]))
        assert rc == 1

    def test_arbitrator_boundary_violation_recorded_in_state(self, tmp_path):
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._strategy_builder_ok_arbitrator_bad(["../README.md"]))
        assert len(runner.state.boundary_violations) >= 1

    def test_out_of_bounds_arbitrator_patch_not_in_state_patches(self, tmp_path):
        """The revised patch must not be appended to state.patches on violation."""
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path)
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        runner.run(_strategy=self._strategy_builder_ok_arbitrator_bad(["/etc/passwd"]))
        # Only the builder patch should be in history (the bad revised is rejected)
        assert all(
            "/etc/passwd" not in f
            for p in runner.state.patches
            for f in p.touched_files
        )

    def test_in_bounds_arbitrator_patch_accepted_normally(self, tmp_path):
        """Arbitrator patch within allowed_roots must still be accepted."""
        from src.implement_loop import (
            CandidatePatch, ImplementCritique, VerifiedImplementCritique,
        )
        from src.implement_runner import ImplementRunner
        cfg = self._make_config(tmp_path)
        strategy = MagicMock()
        strategy.run_builder.return_value = CandidatePatch(
            content="v1", touched_files=("src/a.py",)
        )
        strategy.run_challenger.return_value = [
            ImplementCritique(description="fix x", file_ref="src/a.py", raised_by="challenger")
        ]
        strategy.run_verifier.return_value = [
            VerifiedImplementCritique(
                description="fix x", file_ref="src/a.py", raised_by="challenger", status="valid"
            )
        ]
        # Arbitrator returns a patch within allowed_roots
        strategy.run_arbitrator.return_value = CandidatePatch(
            content="v2", touched_files=("src/a.py",)
        )
        runner = ImplementRunner(config=cfg, backends={}, output_dir=tmp_path)
        rc = runner.run(_strategy=strategy)
        assert rc == 0
        assert runner.state.boundary_violations == []
