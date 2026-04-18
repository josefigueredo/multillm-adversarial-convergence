"""Tests for src.cli — argument parsing, backend detection, logging setup."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import _setup_logging, main


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
                backend: claude
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
        mock_backend.name = "claude"
        mock_backend.cli_executable.return_value = "claude"
        mock_strategy = MagicMock()
        return mock_backend, mock_strategy

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.get_backend")
    def test_backend_not_available(self, mock_get, mock_get_backends, mock_get_strat, config_file):
        mock_backend = MagicMock()
        mock_backend.check_available.return_value = False
        mock_backend.name = "claude"
        mock_backend.cli_executable.return_value = "claude"
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude": mock_backend}
        result = main(["run", "--config", str(config_file)])
        assert result == 1

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_synthesize_mode(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude": mock_backend}
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
        mock_get_backends.return_value = {"claude": mock_backend}
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
    def test_resume_flag_passed_to_researcher(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude": mock_backend}
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
        mock_get_backends.return_value = {"codex": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file), "--backend", "codex"])
        mock_get.assert_called_with("codex")

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_backend_defaults_from_config(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file)])
        mock_get.assert_called_with("claude")

    @patch("src.cli.get_strategy")
    @patch("src.cli.get_backends")
    @patch("src.cli.AutoResearcher")
    @patch("src.cli.get_backend")
    def test_custom_output_dir(self, mock_get, mock_researcher_cls, mock_get_backends, mock_get_strat, config_file, tmp_path):
        mock_backend, mock_strategy = self._mock_cli_deps()
        mock_get.return_value = mock_backend
        mock_get_backends.return_value = {"claude": mock_backend}
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
        mock_get_backends.return_value = {"claude": mock_backend}
        mock_get_strat.return_value = mock_strategy
        mock_researcher_cls.return_value = MagicMock()
        main(["run", "--config", str(config_file)])
        _, kwargs = mock_researcher_cls.call_args
        assert kwargs["backend"] is mock_backend


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
                primary: claude
                research:
                  - claude
                  - gemini
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
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
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
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
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
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
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
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be}

        result = main(["refine", "--config", str(doc_config_file)])

        assert result == 1
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    @patch("src.cli.DocumentRefiner")
    def test_exit_code_2_propagated(self, mock_refiner_cls, mock_get_backends, doc_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
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
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        custom = tmp_path / "myout"
        main(["refine", "--config", str(doc_config_file), "--output", str(custom)])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()
