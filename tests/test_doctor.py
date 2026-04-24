"""Unit tests for src.doctor — doctor config and CLI integration."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config import (
    BackendsConfig,
    ExecutionConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)
from src.doctor import doctor_config_text, DoctorReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> ResearchConfig:
    defaults = dict(
        topic="Compare caching strategies",
        goal="Architecture decision",
        dimensions=("In-memory vs disk", "Latency vs cost"),
        execution=ExecutionConfig(
            backend="claude-cli",
            backends=BackendsConfig(primary="claude-cli"),
            allowed_tools="WebSearch,Grep",
        ),
        scoring=ScoringConfig(),
    )
    defaults.update(kwargs)
    return ResearchConfig(**defaults)


def _make_config_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "research.yaml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# DoctorReport type contract
# ---------------------------------------------------------------------------

class TestDoctorReport:
    def test_has_text_and_exit_code(self):
        report = DoctorReport(text="ok", exit_code=0)
        assert report.text == "ok"
        assert report.exit_code == 0

    def test_exit_code_1_for_issues(self):
        report = DoctorReport(text="warn", exit_code=1)
        assert report.exit_code == 1


# ---------------------------------------------------------------------------
# doctor_config_text — basic structure
# ---------------------------------------------------------------------------

class TestDoctorConfigTextStructure:
    def test_returns_doctor_report(self):
        config = _make_config()
        result = doctor_config_text(config)
        assert isinstance(result, DoctorReport)

    def test_text_is_nonempty_string(self):
        result = doctor_config_text(_make_config())
        assert isinstance(result.text, str)
        assert len(result.text) > 0

    def test_contains_health_summary(self):
        result = doctor_config_text(_make_config())
        assert "HEALTH" in result.text

    def test_contains_enforcement_section(self):
        result = doctor_config_text(_make_config())
        assert "SECURITY ENFORCEMENT STATUS" in result.text

    def test_contains_backend_validity_section(self):
        result = doctor_config_text(_make_config())
        assert "BACKEND" in result.text

    def test_healthy_config_exits_0(self):
        result = doctor_config_text(_make_config())
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Security enforcement truth table
# ---------------------------------------------------------------------------

class TestSecurityEnforcementTable:
    def test_allow_host_bash_shown_as_enforced(self):
        result = doctor_config_text(_make_config())
        assert "allow_host_bash" in result.text
        assert "enforced" in result.text.lower()

    def test_filesystem_access_shown_as_enforced(self):
        result = doctor_config_text(_make_config())
        assert "filesystem_access" in result.text
        assert "enforced" in result.text.lower()

    def test_tool_execution_mode_sandboxed_shown_as_declared_only(self):
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            )
        )
        result = doctor_config_text(config)
        assert "declared-only" in result.text.lower() or "declared only" in result.text.lower()

    def test_network_access_shown_as_declared_only(self):
        config = _make_config(
            security=SecurityConfig(
                sandbox=SandboxConfig(network_access="web_only"),
            )
        )
        result = doctor_config_text(config)
        assert "network_access" in result.text
        assert "declared-only" in result.text.lower() or "declared only" in result.text.lower()

    def test_each_enforced_field_has_label(self):
        result = doctor_config_text(_make_config())
        # At minimum both enforced fields must appear
        text = result.text
        assert "allow_host_bash" in text
        assert "filesystem_access" in text


# ---------------------------------------------------------------------------
# Backend validity checks
# ---------------------------------------------------------------------------

class TestBackendValidity:
    def test_valid_backend_is_reported_valid(self):
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch",
            )
        )
        result = doctor_config_text(config)
        assert "claude-cli" in result.text

    def test_unknown_backend_produces_warning(self):
        config = _make_config(
            execution=ExecutionConfig(
                backend="nonexistent-backend-xyz",
                backends=BackendsConfig(primary="nonexistent-backend-xyz"),
                allowed_tools="",
            )
        )
        result = doctor_config_text(config)
        assert "nonexistent-backend-xyz" in result.text
        # Should flag as unknown/invalid
        text_lower = result.text.lower()
        assert "unknown" in text_lower or "invalid" in text_lower or "not found" in text_lower or "warn" in text_lower

    def test_unknown_backend_exits_1(self):
        config = _make_config(
            execution=ExecutionConfig(
                backend="nonexistent-backend-xyz",
                backends=BackendsConfig(primary="nonexistent-backend-xyz"),
                allowed_tools="",
            )
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Operator risk notes
# ---------------------------------------------------------------------------

class TestOperatorRiskNotes:
    def test_bash_in_tools_with_allow_host_bash_true_shows_risk_note(self):
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Bash,WebSearch",
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        # Should note that host shell is exposed
        assert "bash" in text_lower
        assert (
            "risk" in text_lower
            or "warn" in text_lower
            or "host shell" in text_lower
            or "exposed" in text_lower
            or "note" in text_lower
        )

    def test_bash_exposure_risk_exits_1(self):
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Bash,WebSearch",
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1

    def test_allow_host_bash_false_with_bash_in_tools_no_risk(self):
        config = _make_config(
            security=SecurityConfig(allow_host_bash=False),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Bash,WebSearch",
            ),
        )
        result = doctor_config_text(config)
        # allow_host_bash is False so enforcement is active — no "host shell exposed" risk
        text_lower = result.text.lower()
        assert "host shell exposed" not in text_lower

    def test_sandboxed_declared_only_note_appears(self):
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "declared" in text_lower
        assert "sandbox" in text_lower

    def test_sandboxed_declared_only_exits_1(self):
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1

    def test_network_policy_declared_only_exits_1(self):
        config = _make_config(
            security=SecurityConfig(
                sandbox=SandboxConfig(network_access="web_only"),
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1

    def test_no_risk_notes_section_when_clean(self):
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch",  # No Bash
            ),
        )
        result = doctor_config_text(config)
        # Healthy config → exit 0
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# CLI integration — autoresearch doctor config --config <path>
# ---------------------------------------------------------------------------

class TestDoctorConfigCLI:
    def test_cli_exits_0_for_valid_config(self, tmp_path):
        from src.cli import main
        cfg = _make_config_yaml(tmp_path, """\
            research:
              topic: "Test topic"
              goal: "Test goal"
              execution:
                backend: claude-cli
                allowed_tools: "WebSearch,Grep"
              security:
                allow_host_bash: false
        """)
        rc = main(["doctor", "config", "--config", str(cfg)])
        assert rc == 0

    def test_cli_exits_1_for_missing_file(self, tmp_path):
        from src.cli import main
        rc = main(["doctor", "config", "--config", str(tmp_path / "no_such.yaml")])
        assert rc == 1

    def test_cli_prints_output(self, tmp_path, capsys):
        from src.cli import main
        cfg = _make_config_yaml(tmp_path, """\
            research:
              topic: "Test"
              goal: "Test goal"
              execution:
                backend: claude-cli
                allowed_tools: "WebSearch,Grep"
              security:
                allow_host_bash: false
        """)
        main(["doctor", "config", "--config", str(cfg)])
        captured = capsys.readouterr()
        assert "HEALTH" in captured.out
        assert "SECURITY ENFORCEMENT STATUS" in captured.out

    def test_cli_exits_1_for_unknown_backend_in_yaml(self, tmp_path):
        from src.cli import main
        cfg = _make_config_yaml(tmp_path, """\
            research:
              topic: "Test"
              goal: "Test goal"
              execution:
                backend: totally-fake-backend-xyz
        """)
        rc = main(["doctor", "config", "--config", str(cfg)])
        assert rc == 1


# ---------------------------------------------------------------------------
# doctor_output_text — output directory diagnostics
# ---------------------------------------------------------------------------

def _write_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_complete_run(output_dir: Path) -> None:
    """Populate output_dir with all artifacts of a successful run."""
    from src.run_paths import RunPaths
    import json

    paths = RunPaths.for_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths.iterations_dir.mkdir(parents=True, exist_ok=True)
    _write_file(paths.iterations_dir / "iter_001.md", "# iteration 1")
    _write_file(paths.iterations_dir / "iter_002.md", "# iteration 2")
    _write_file(paths.synthesis, "# synthesis")
    _write_file(paths.knowledge_base, "# kb")
    _write_file(paths.results, "score\t0.85")
    _write_file(paths.report_html, "<html/>")
    _write_file(paths.audit_trail, '{"event":"run_started"}\n')
    _write_file(paths.effective_config, json.dumps({"security": {}}))
    _write_file(paths.metrics, json.dumps({"best_score": 0.85, "run_status": "complete"}))
    _write_file(paths.manifest, json.dumps({"run_id": "test-run"}))


def _make_partial_run(output_dir: Path) -> None:
    """Populate output_dir with only iteration state (interrupted before synthesis)."""
    from src.run_paths import RunPaths

    paths = RunPaths.for_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths.iterations_dir.mkdir(parents=True, exist_ok=True)
    _write_file(paths.iterations_dir / "iter_001.md", "# iteration 1")
    _write_file(paths.knowledge_base, "# kb")
    _write_file(paths.effective_config, '{}')


class TestDoctorOutputText:
    def test_returns_doctor_report(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert isinstance(result, DoctorReport)

    def test_complete_run_exits_0(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 0

    def test_complete_run_health_ok(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert "HEALTH" in result.text
        assert "OK" in result.text

    def test_output_dir_not_found_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        result = doctor_output_text(tmp_path / "no_such_dir")
        assert result.exit_code == 1

    def test_output_dir_not_found_has_error_text(self, tmp_path):
        from src.doctor import doctor_output_text
        result = doctor_output_text(tmp_path / "no_such_dir")
        assert "not found" in result.text.lower() or "error" in result.text.lower()

    def test_contains_artifact_status_section(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert "ARTIFACT" in result.text

    def test_contains_resumability_section(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert "RESUM" in result.text

    def test_contains_synthesis_readiness_section(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert "SYNTHESIS" in result.text or "REGENERAT" in result.text

    def test_shows_iteration_count(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert "2" in result.text  # 2 iteration files

    def test_partial_run_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_partial_run(tmp_path)
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_partial_run_shows_warning(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_partial_run(tmp_path)
        result = doctor_output_text(tmp_path)
        text_lower = result.text.lower()
        assert "partial" in text_lower or "warn" in text_lower or "incomplete" in text_lower

    def test_empty_dir_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        empty = tmp_path / "empty_run"
        empty.mkdir()
        result = doctor_output_text(empty)
        assert result.exit_code == 1

    def test_missing_effective_config_is_flagged(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        (tmp_path / "effective_config.json").unlink()
        result = doctor_output_text(tmp_path)
        text_lower = result.text.lower()
        assert "effective_config" in text_lower

    def test_missing_effective_config_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        (tmp_path / "effective_config.json").unlink()
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_synthesis_without_report_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        (tmp_path / "report.html").unlink()
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_run_status_shown_when_present(self, tmp_path):
        from src.doctor import doctor_output_text
        import json
        _make_complete_run(tmp_path)
        (tmp_path / "metrics.json").write_text(
            json.dumps({"best_score": 0.92, "run_status": "complete"}),
            encoding="utf-8",
        )
        result = doctor_output_text(tmp_path)
        assert "complete" in result.text.lower()
        assert "0.92" in result.text


class TestDoctorOutputCLI:
    def test_cli_exits_0_for_complete_run(self, tmp_path):
        from src.cli import main
        _make_complete_run(tmp_path)
        rc = main(["doctor", "output", "--output", str(tmp_path)])
        assert rc == 0

    def test_cli_exits_1_for_missing_dir(self, tmp_path):
        from src.cli import main
        rc = main(["doctor", "output", "--output", str(tmp_path / "no_such")])
        assert rc == 1

    def test_cli_prints_output(self, tmp_path, capsys):
        from src.cli import main
        _make_complete_run(tmp_path)
        main(["doctor", "output", "--output", str(tmp_path)])
        out = capsys.readouterr().out
        assert "HEALTH" in out
        assert "ARTIFACT" in out

    def test_cli_exits_1_for_partial_run(self, tmp_path):
        from src.cli import main
        _make_partial_run(tmp_path)
        rc = main(["doctor", "output", "--output", str(tmp_path)])
        assert rc == 1

