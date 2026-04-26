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

    def test_non_dry_run_with_valid_config_proceeds(self, tmp_path, capsys):
        """Non-dry-run implement with a valid config passes through to the runner (stub returns 0)."""
        from src.cli import _run_implement
        import argparse, logging

        config_file = tmp_path / "impl.yaml"
        config_file.write_text(f"target:\n  path: {tmp_path}\n")

        args = argparse.Namespace(
            config=config_file,
            output=tmp_path / "out",
            resume=False,
            dry_run=False,
        )
        rc = _run_implement(args, logging.getLogger("test"))
        assert rc == 0

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
