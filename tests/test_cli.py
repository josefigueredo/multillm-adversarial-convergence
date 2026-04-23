"""Tests for src.cli — argument parsing, backend detection, logging setup."""
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import _build_parser, _setup_logging, main


# ---------------------------------------------------------------------------
# _setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def test_verbose(self):
        import logging
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        _setup_logging(verbose=True)
        assert root.level <= logging.DEBUG

    def test_normal(self):
        import logging
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)
        _setup_logging(verbose=False)
        assert root.level <= logging.INFO


class TestParserSmoke:
    def test_subcommand_help_lists_dry_run_flags(self, capsys):
        parser = _build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--help"])
        run_help = capsys.readouterr().out
        assert "--dry-run" in run_help

        with pytest.raises(SystemExit):
            parser.parse_args(["refine", "--help"])
        refine_help = capsys.readouterr().out
        assert "--dry-run" in refine_help

        with pytest.raises(SystemExit):
            parser.parse_args(["plan", "--help"])
        plan_help = capsys.readouterr().out
        assert "--dry-run" in plan_help


# ---------------------------------------------------------------------------
# run subcommand
# ---------------------------------------------------------------------------

class TestRunSubcommand:
    @pytest.fixture
    def config_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "test.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                max_iterations: 1
                backend: claude-cli
                model: sonnet
        """), encoding="utf-8")
        return p

    def test_missing_config(self, tmp_path):
        result = main(["run", "--config", str(tmp_path / "nonexistent.yaml")])
        assert result == 1

    def test_malformed_config(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("not_research: true\n", encoding="utf-8")
        result = main(["run", "--config", str(bad)])
        assert result == 1

    def _mock_cli_deps(self):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = True
        mock_backend.name = "claude-cli"
        mock_backend.cli_executable.return_value = "claude-cli"
        mock_strategy = MagicMock()
        return mock_backend, mock_strategy

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.get_backend")
    def test_backend_not_available(self, mock_get, mock_get_backends, mock_get_strat, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = False
        mock_backend.name = "claude-cli"
        mock_backend.cli_executable.return_value = "claude-cli"
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        result = main(["run", "--config", str(config_file)])
        assert result == 1

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_synthesize_mode(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["run", "--config", str(config_file), "--synthesize"])
        assert result == 0
        mock_instance.synthesize_only.assert_called_once()

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_run_mode(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_instance = MagicMock()
        mock_researcher_cls.return_value = mock_instance
        result = main(["run", "--config", str(config_file)])
        assert result == 0
        mock_instance.run.assert_called_once()
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["resume"] is False
        assert kwargs["config_path"] == config_file

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_dry_run_mode_skips_researcher_execution(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy

        result = main(["run", "--config", str(config_file), "--dry-run"])

        assert result == 0
        mock_researcher_cls.assert_not_called()

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.get_backend")
    def test_dry_run_fails_when_backend_unavailable(self, mock_get, mock_get_backends, mock_get_strat, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = False
        mock_backend.name = "claude-cli"
        mock_backend.cli_executable.return_value = "claude-cli"
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = MagicMock()

        result = main(["run", "--config", str(config_file), "--dry-run"])

        assert result == 1

    def test_dry_run_rejects_resume(self, config_file):
        result = main(["run", "--config", str(config_file), "--dry-run", "--resume"])
        assert result == 1

    def test_dry_run_rejects_synthesize(self, config_file):
        result = main(["run", "--config", str(config_file), "--dry-run", "--synthesize"])
        assert result == 1

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.get_backend")
    def test_dry_run_does_not_create_output_dir(self, mock_get, mock_get_backends, mock_get_strat, config_file, tmp_path):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        output_dir = tmp_path / "dry-output"

        result = main(["run", "--config", str(config_file), "--dry-run", "--output", str(output_dir)])

        assert result == 0
        assert not output_dir.exists()

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.get_backend")
    def test_dry_run_logs_summary(self, mock_get, mock_get_backends, mock_get_strat, config_file, capsys):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy

        result = main(["run", "--config", str(config_file), "--dry-run"])
        captured = capsys.readouterr()

        assert result == 0
        assert "DRY RUN OK" in captured.err
        assert "planned artifacts:" in captured.err
        assert "resolved backends: claude-cli" in captured.err

    @patch("src.cli.instantiate_provider_backends")
    @patch("src.cli.AutoResearcher")
    def test_dry_run_uses_provider_instances_when_declared(self, mock_researcher_cls, mock_instantiate, tmp_path):
        config_file = tmp_path / "provider_run.yaml"
        config_file.write_text(textwrap.dedent("""\
            research:
              topic: "Provider test"
              execution:
                strategy: ensemble
                providers:
                  primary_reasoner:
                    adapter: claude-cli
                    model: opus
                  fast_research:
                    adapter: codex-cli
                    model: gpt-5.4
                backends:
                  primary: primary_reasoner
                  research:
                    - primary_reasoner
                    - fast_research
        """), encoding="utf-8")

        be1 = MagicMock()
        be1.check_available.return_value = True
        be1.cli_executable.return_value = "claude"
        be2 = MagicMock()
        be2.check_available.return_value = True
        be2.cli_executable.return_value = "codex"
        mock_instantiate.return_value = {
            "primary_reasoner": be1,
            "fast_research": be2,
        }

        result = main(["run", "--config", str(config_file), "--dry-run"])

        assert result == 0
        mock_instantiate.assert_called_once()
        mock_researcher_cls.assert_not_called()

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_resume_flag_passed_to_researcher(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file), "--resume"])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["resume"] is True

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_flag_overrides_config(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"codex-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file), "--backend", "codex-cli"])
        mock_get.assert_called_with("codex-cli")

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_defaults_from_config(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file)])
        mock_get.assert_called_with("claude-cli")

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_custom_output_dir(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file, tmp_path):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        custom = tmp_path / "custom_out"
        main(["run", "--config", str(config_file), "--output", str(custom)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_passed_to_researcher(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude-cli": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["backend"] is mock_backend

    @patch("src.cli.instantiate_provider_backends")
    @patch("src.cli.AutoResearcher")
    def test_run_uses_provider_instances_when_declared(self, mock_researcher_cls, mock_instantiate, tmp_path):
        config_file = tmp_path / "provider_run.yaml"
        config_file.write_text(textwrap.dedent("""\
            research:
              topic: "Provider test"
              execution:
                strategy: ensemble
                providers:
                  primary_reasoner:
                    adapter: claude-cli
                    model: opus
                  fast_research:
                    adapter: codex-cli
                    model: gpt-5.4
                backends:
                  primary: primary_reasoner
                  research:
                    - primary_reasoner
                    - fast_research
        """), encoding="utf-8")

        be1 = MagicMock()
        be1.check_available.return_value = True
        be1.cli_executable.return_value = "claude"
        be2 = MagicMock()
        be2.check_available.return_value = True
        be2.cli_executable.return_value = "codex"
        mock_instantiate.return_value = {
            "primary_reasoner": be1,
            "fast_research": be2,
        }
        mock_instance = MagicMock()
        mock_instance.run.return_value = None
        mock_researcher_cls.return_value = mock_instance

        result = main(["run", "--config", str(config_file)])

        assert result == 0
        mock_instantiate.assert_called_once()
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["backend"] is be1
        assert kwargs["backends"] == {"primary_reasoner": be1, "fast_research": be2}


# ---------------------------------------------------------------------------
# refine subcommand
# ---------------------------------------------------------------------------

class TestRefineSubcommand:
    @pytest.fixture
    def doc_config_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "doc.yaml"
        p.write_text(textwrap.dedent("""\
            document:
              topic: "Test PRD"
              goal: "Build something"
              primary_artifact: "PRD.md"
              backends:
                primary: claude-cli
                research:
                  - claude-cli
                  - gemini-cli
        """), encoding="utf-8")
        return p

    def test_missing_config(self, tmp_path):
        result = main(["refine", "--config", str(tmp_path / "nonexistent.yaml")])
        assert result == 1

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_refine_calls_refiner_run(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        result = main(["refine", "--config", str(doc_config_file)])

        assert result == 0
        mock_instance.run.assert_called_once_with(interactive=True)

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_no_interactive_flag(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["refine", "--config", str(doc_config_file), "--no-interactive"])

        mock_instance.run.assert_called_once_with(interactive=False)

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_resume_flag_passed_to_refiner(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["refine", "--config", str(doc_config_file), "--resume"])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["resume"] is True

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_backend_unavailable_returns_1(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = False
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be}

        result = main(["refine", "--config", str(doc_config_file)])

        assert result == 1
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_exit_code_2_propagated(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 2
        mock_refiner_cls.return_value = mock_instance

        result = main(["refine", "--config", str(doc_config_file)])

        assert result == 2

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_custom_output_dir(self, mock_refiner_cls, mock_get_backends, doc_config_file, tmp_path):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        custom = tmp_path / "myout"
        main(["refine", "--config", str(doc_config_file), "--output", str(custom)])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_refine_dry_run_skips_refiner_execution(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}

        result = main(["refine", "--config", str(doc_config_file), "--dry-run"])

        assert result == 0
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    def test_refine_dry_run_does_not_create_output_dir(self, mock_get_backends, doc_config_file, tmp_path):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        output_dir = tmp_path / "refine-dry"

        result = main(["refine", "--config", str(doc_config_file), "--dry-run", "--output", str(output_dir)])

        assert result == 0
        assert not output_dir.exists()

    @patch("src.cli.get_backends")
    def test_refine_dry_run_logs_summary(self, mock_get_backends, doc_config_file, capsys):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}

        result = main(["refine", "--config", str(doc_config_file), "--dry-run"])
        captured = capsys.readouterr()

        assert result == 0
        assert "DRY RUN OK" in captured.err
        assert "mode: refine" in captured.err
        assert "resolved backends: claude-cli, gemini-cli" in captured.err


# ---------------------------------------------------------------------------
# plan subcommand
# ---------------------------------------------------------------------------

class TestPlanSubcommand:
    @pytest.fixture
    def plan_config_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "plan.yaml"
        p.write_text(textwrap.dedent("""\
            plan:
              topic: "Test Plan"
              goal: "Build something"
              backends:
                primary: claude-cli
                research:
                  - claude-cli
                  - gemini-cli
        """), encoding="utf-8")
        return p

    def test_missing_config_returns_1(self, tmp_path):
        result = main(["plan", "--config", str(tmp_path / "nonexistent.yaml")])
        assert result == 1

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_calls_refiner_run(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        result = main(["plan", "--config", str(plan_config_file)])

        assert result == 0
        mock_instance.run.assert_called_once_with(interactive=True)

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_no_interactive_flag(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["plan", "--config", str(plan_config_file), "--no-interactive"])

        mock_instance.run.assert_called_once_with(interactive=False)

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_resume_flag(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["plan", "--config", str(plan_config_file), "--resume"])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["resume"] is True

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_backend_unavailable_returns_1(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = False
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be}

        result = main(["plan", "--config", str(plan_config_file)])

        assert result == 1
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_custom_output_dir(self, mock_refiner_cls, mock_get_backends, plan_config_file, tmp_path):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        custom = tmp_path / "my_output"
        main(["plan", "--config", str(plan_config_file), "--output", str(custom)])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_exit_code_2_propagated(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 2
        mock_refiner_cls.return_value = mock_instance

        result = main(["plan", "--config", str(plan_config_file), "--no-interactive"])

        assert result == 2

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_dry_run_skips_refiner_execution(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}

        result = main(["plan", "--config", str(plan_config_file), "--dry-run"])

        assert result == 0
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    def test_plan_dry_run_does_not_create_output_dir(self, mock_get_backends, plan_config_file, tmp_path):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}
        output_dir = tmp_path / "plan-dry"

        result = main(["plan", "--config", str(plan_config_file), "--dry-run", "--output", str(output_dir)])

        assert result == 0
        assert not output_dir.exists()

    @patch("src.cli.get_backends")
    def test_plan_dry_run_logs_summary(self, mock_get_backends, plan_config_file, capsys):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude-cli"
        mock_get_backends.return_value = {"claude-cli": mock_be, "gemini-cli": mock_be}

        result = main(["plan", "--config", str(plan_config_file), "--dry-run"])
        captured = capsys.readouterr()

        assert result == 0
        assert "DRY RUN OK" in captured.err
        assert "mode: plan" in captured.err
        assert "resolved backends: claude-cli, gemini-cli" in captured.err
