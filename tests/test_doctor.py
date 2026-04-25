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

    def test_tool_execution_mode_sandboxed_shown_as_dispatch_enforced_when_active(self):
        """sandbox_active=True → truth table must show dispatch-enforced, not declared-only."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            )
        )
        result = doctor_config_text(config)
        assert "dispatch-enforced" in result.text.lower() or "dispatch enforced" in result.text.lower()

    def test_tool_execution_mode_sandboxed_not_active_shows_declared_intent(self):
        """sandbox mode=off + tool_execution_mode=sandboxed → declared intent (no active enforcement)."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="off"),  # NOT active
            )
        )
        result = doctor_config_text(config)
        # should say declared intent, not dispatch-enforced
        assert "dispatch-enforced" not in result.text.lower()

    def test_network_access_dispatch_enforced_when_sandbox_active(self):
        """sandbox_active=True + non-unrestricted network_access → dispatch-enforced in table."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls", network_access="web_only"),
            )
        )
        result = doctor_config_text(config)
        assert "network_access" in result.text
        assert "dispatch-enforced" in result.text.lower() or "dispatch enforced" in result.text.lower()

    def test_network_access_dispatch_enforced_is_healthy(self):
        """sandbox_active=True + non-unrestricted → healthy run (exit_code=0)."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls", network_access="none"),
            )
        )
        result = doctor_config_text(config)
        assert result.exit_code == 0

    def test_network_access_no_effect_note_when_not_sandbox_active(self):
        """sandbox_active=False + non-unrestricted network_access → warning about no effect."""
        config = _make_config(
            security=SecurityConfig(
                sandbox=SandboxConfig(network_access="web_only"),  # direct mode → sandbox_active=False
            )
        )
        result = doctor_config_text(config)
        assert "network_access" in result.text
        text_lower = result.text.lower()
        # Must indicate the policy has no effect without sandbox_active
        assert "sandbox_active" in text_lower or "no effect" in text_lower or "without" in text_lower

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

    def test_sandboxed_active_is_healthy_no_warning(self):
        """sandbox_active=True with default (unrestricted) network → no risk notes → exit_code=0."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),  # sandbox_active=True
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 0

    def test_sandboxed_mode_off_produces_warning(self):
        """tool_execution_mode=sandboxed but mode=off → sandbox not active → warning."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="off"),
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "sandbox" in text_lower
        assert result.exit_code == 1

    def test_network_policy_no_effect_without_sandbox_active_exits_1(self):
        """network_access set but sandbox_active=False → no operational effect → warning → exit_code=1."""
        config = _make_config(
            security=SecurityConfig(
                sandbox=SandboxConfig(network_access="web_only"),  # direct mode → sandbox_active=False
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
# M5 Step 4: diagnostics for env shaping, tool coverage, unclassified tools
# ---------------------------------------------------------------------------

class TestDoctorM5Coverage:
    """Doctor surfaces M5 sandbox coverage: env shaping, tool classification, gaps."""

    # -- env shaping status ------------------------------------------------

    def test_env_shaping_shown_as_active_when_sandbox_active(self):
        """sandbox_active=True → doctor output surfaces env shaping as active."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "env shaping" in text_lower or "environment shaping" in text_lower
        # Must indicate it is active
        assert "active" in text_lower

    def test_env_shaping_shown_as_inactive_in_direct_mode(self):
        """tool_execution_mode=direct → doctor labels env shaping inactive with 'direct mode'."""
        config = _make_config(
            security=SecurityConfig(tool_execution_mode="direct"),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "env shaping" in text_lower or "environment shaping" in text_lower
        assert "inactive" in text_lower
        assert "direct" in text_lower

    def test_env_shaping_shown_as_inactive_sandbox_declared_but_not_active(self):
        """sandboxed + mode=off → inactive; must NOT say 'direct mode'."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="off"),  # declared but not active
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "env shaping" in text_lower or "environment shaping" in text_lower
        assert "inactive" in text_lower
        # Must distinguish from direct mode — sandbox intent is declared
        assert "not active" in text_lower or "declared" in text_lower or "sandbox" in text_lower
        # Must NOT claim this is direct mode
        assert "direct mode" not in text_lower

    # -- tool coverage section ---------------------------------------------

    def test_tool_coverage_section_present(self):
        """Doctor output contains a tool coverage or capability section."""
        result = doctor_config_text(_make_config())
        text_lower = result.text.lower()
        assert "tool" in text_lower and ("coverage" in text_lower or "classif" in text_lower)

    def test_classified_tools_appear_in_coverage(self):
        """Tools from allowed_tools that are in the registry appear in coverage output."""
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch,Grep",
            ),
        )
        result = doctor_config_text(config)
        assert "WebSearch" in result.text
        assert "Grep" in result.text

    def test_unclassified_tool_shown_in_coverage(self):
        """A tool not in the registry appears in coverage output with unclassified label."""
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch,FancyNewTool",
            ),
        )
        result = doctor_config_text(config)
        assert "FancyNewTool" in result.text
        text_lower = result.text.lower()
        assert "unclassified" in text_lower

    # -- unclassified tool risk note ---------------------------------------

    def test_unclassified_tool_in_sandbox_exits_1(self):
        """sandbox_active=True + unclassified tool → doctor exits 1 (will be denied at runtime)."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Read,FancyNewTool",
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1

    def test_unclassified_tool_in_sandbox_shows_warning(self):
        """sandbox_active=True + unclassified tool → doctor shows warning about denial."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Read,FancyNewTool",
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "FancyNewTool".lower() in text_lower
        assert "unclassified" in text_lower or "denied" in text_lower

    def test_unclassified_tool_in_direct_mode_is_healthy(self):
        """sandbox_active=False + unclassified tool → no warning (direct mode passes through)."""
        config = _make_config(
            security=SecurityConfig(tool_execution_mode="direct"),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Read,FancyNewTool",
            ),
        )
        result = doctor_config_text(config)
        # Direct mode: unclassified tools pass through → no warning about them
        assert result.exit_code == 0

    # -- network coverage honesty ------------------------------------------

    def test_network_enforcement_dispatch_level_noted(self):
        """Doctor output mentions that network enforcement is dispatch-level (not OS-level)."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls", network_access="web_only"),
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "dispatch" in text_lower

    def test_all_classified_tools_no_unclassified_warning(self):
        """All tools classified → no unclassified warning even in sandbox mode."""
        config = _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch,Read,Grep",  # all classified
            ),
        )
        result = doctor_config_text(config)
        # No unclassified tools → exit 0 (no warnings)
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

    def test_reused_artifacts_reflect_actual_presence(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_partial_run(tmp_path)
        # _make_partial_run includes knowledge_base.md but NOT results.tsv
        result = doctor_output_text(tmp_path)
        reuse_line = next(
            (l for l in result.text.splitlines() if "reused on resume" in l), ""
        )
        assert "knowledge_base.md" in reuse_line
        assert "results.tsv" not in reuse_line

    def test_reused_artifacts_omit_missing_knowledge_base(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_partial_run(tmp_path)
        (tmp_path / "knowledge_base.md").unlink()
        result = doctor_output_text(tmp_path)
        reuse_line = next(
            (l for l in result.text.splitlines() if "reused on resume" in l), ""
        )
        assert "knowledge_base.md" not in reuse_line

    def test_reused_artifacts_include_results_when_present(self, tmp_path):
        from src.doctor import doctor_output_text
        from src.run_paths import RunPaths
        _make_partial_run(tmp_path)
        _write_file(RunPaths.for_output_dir(tmp_path).results, "score\t0.7")
        result = doctor_output_text(tmp_path)
        reuse_line = next(
            (l for l in result.text.splitlines() if "reused on resume" in l), ""
        )
        assert "results.tsv" in reuse_line


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



# ---------------------------------------------------------------------------
# MM06 Step 4 — capability-based host-shell risk note
# ---------------------------------------------------------------------------

class TestDispatchContractRiskNotes:
    """Risk notes must use capability metadata, not hardcoded tool names."""

    def test_custom_host_shell_tool_triggers_risk_note(self, monkeypatch):
        """A non-Bash tool with uses_host_shell=True must trigger the host-shell risk note."""
        from src import tool_capabilities as tc
        monkeypatch.setitem(
            tc._TOOL_CAPABILITIES,
            "CustomShell",
            tc.ToolCapabilities(uses_host_shell=True),
        )
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="CustomShell,Read",
            ),
        )
        result = doctor_config_text(config)
        text_lower = result.text.lower()
        assert "host shell" in text_lower or "exposed" in text_lower or "host-shell" in text_lower
        assert result.exit_code == 1

    def test_bash_still_triggers_risk_note_via_capability(self, monkeypatch):
        """Bash still triggers the risk note after the capability-based fix."""
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Bash,Read",
            ),
        )
        result = doctor_config_text(config)
        assert result.exit_code == 1
        assert "host shell" in result.text.lower() or "exposed" in result.text.lower()

    def test_non_shell_tool_does_not_trigger_host_shell_risk(self):
        """A non-host-shell tool must not trigger the host-shell risk note."""
        config = _make_config(
            security=SecurityConfig(allow_host_bash=True),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch,Read",
            ),
        )
        result = doctor_config_text(config)
        # With allow_host_bash=True but no shell-capable tools, no host-shell risk note
        text_lower = result.text.lower()
        assert "host shell is exposed" not in text_lower
        assert "host shell exposed" not in text_lower


# ---------------------------------------------------------------------------
# MM06 Step 5 — isolation maturity diagnostics
# ---------------------------------------------------------------------------

class TestDoctorMM06Diagnostics:
    """Doctor surfaces MM06 isolation maturity: backend type, env policy, coverage stats."""

    def _sandbox_active_config(self, tools: str = "Read,Grep") -> ResearchConfig:
        return _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="tool_calls"),
            ),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools=tools,
            ),
        )

    def _sandbox_declared_not_active_config(self, tools: str = "Read,Grep") -> ResearchConfig:
        return _make_config(
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=SandboxConfig(mode="off"),  # declared but not active
            ),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools=tools,
            ),
        )

    def _direct_config(self, tools: str = "Read,Grep") -> ResearchConfig:
        return _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools=tools,
            ),
        )

    # -- sandbox backend type (3 states) -----------------------------------

    def test_sandbox_backend_type_shown_when_sandbox_active(self):
        """sandbox_active=True → local-process backend type surfaced."""
        result = doctor_config_text(self._sandbox_active_config())
        text_lower = result.text.lower()
        assert "local-process" in text_lower or "localprocessbackend" in text_lower

    def test_sandbox_backend_type_shown_when_declared_not_active(self):
        """sandboxed declared but not active → local-process still mentioned (as declared)."""
        result = doctor_config_text(self._sandbox_declared_not_active_config())
        text_lower = result.text.lower()
        assert "local-process" in text_lower or "localprocessbackend" in text_lower

    def test_sandbox_backend_type_na_in_direct_mode(self):
        """direct mode → sandbox backend shown as N/A (no substrate active)."""
        result = doctor_config_text(self._direct_config())
        assert "N/A" in result.text

    def test_sandbox_backend_line_not_na_when_sandbox_active(self):
        """sandbox_active=True → the sandbox backend line must not say N/A."""
        result = doctor_config_text(self._sandbox_active_config())
        lines = result.text.splitlines()
        backend_lines = [l for l in lines if "sandbox backend" in l.lower()]
        assert backend_lines, "Expected a 'sandbox backend:' line in output"
        assert "N/A" not in backend_lines[0]

    # -- env policy summary (3 states) ------------------------------------

    def test_env_policy_summary_shown_when_sandbox_active(self):
        """sandbox_active=True → env policy line with required/denied counts surfaced."""
        result = doctor_config_text(self._sandbox_active_config())
        text_lower = result.text.lower()
        assert "env policy" in text_lower

    def test_env_policy_shows_required_and_denied_counts(self):
        """sandbox_active=True → required and denied counts visible in env policy line."""
        result = doctor_config_text(self._sandbox_active_config())
        text_lower = result.text.lower()
        assert "required" in text_lower
        assert "denied" in text_lower

    def test_env_policy_shows_effective_count_when_sandbox_active(self):
        """sandbox_active=True → effective allowlist size shown."""
        result = doctor_config_text(self._sandbox_active_config())
        assert "effective" in result.text.lower()

    def test_env_policy_shown_when_sandbox_declared_not_active(self):
        """sandbox declared but not active → env policy line shown (as default/inactive)."""
        result = doctor_config_text(self._sandbox_declared_not_active_config())
        assert "env policy" in result.text.lower()

    def test_env_policy_not_shown_in_direct_mode(self):
        """direct mode → env policy line NOT shown (no sandbox substrate)."""
        result = doctor_config_text(self._direct_config())
        assert "env policy" not in result.text.lower()

    # -- capability coverage stats ----------------------------------------

    def test_coverage_stats_line_present(self):
        """A 'tool coverage:' summary line is always shown."""
        result = doctor_config_text(self._sandbox_active_config())
        assert "tool coverage" in result.text.lower()

    def test_coverage_stats_shows_fraction_all_classified(self):
        """All classified tools → coverage fraction shown (e.g. '2/2 classified')."""
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Read,Grep",  # both classified
            ),
        )
        result = doctor_config_text(config)
        assert "2/2" in result.text

    def test_coverage_stats_shows_fraction_with_unclassified(self):
        """Partially classified tools → fraction reflects actual counts (e.g. '1/2')."""
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="Read,UnknownTool",  # 1 classified, 1 not
            ),
        )
        result = doctor_config_text(config)
        assert "1/2" in result.text

    def test_coverage_stats_empty_tools_does_not_crash(self):
        """Empty allowed_tools → coverage stats render cleanly as 0/0."""
        config = _make_config(
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="",
            ),
        )
        result = doctor_config_text(config)
        assert "tool coverage" in result.text.lower()
        assert "0/0" in result.text

    # -- write-intent audit -----------------------------------------------

    def test_write_intent_audit_shown_when_sandbox_active(self):
        """sandbox_active=True → write-intent audit note present in output."""
        result = doctor_config_text(self._sandbox_active_config(tools="Read,Write"))
        text_lower = result.text.lower()
        assert "write-intent" in text_lower or ("write" in text_lower and "audit" in text_lower)

    def test_write_intent_described_as_audit_not_deny(self):
        """Write-intent audit note must say 'audit' — it is NOT a deny gate."""
        result = doctor_config_text(self._sandbox_active_config(tools="Read,Write"))
        lines = result.text.splitlines()
        write_intent_lines = [l for l in lines if "write-intent" in l.lower()]
        assert write_intent_lines, "Expected a 'write-intent' line when sandbox_active"
        for line in write_intent_lines:
            assert "audit" in line.lower(), "Write-intent line must mention 'audit'"

    def test_write_intent_absent_in_direct_mode(self):
        """direct mode → no write-intent audit line (dispatch audit events not active)."""
        result = doctor_config_text(self._direct_config(tools="Read,Write"))
        lines = result.text.splitlines()
        write_intent_lines = [l for l in lines if "write-intent" in l.lower()]
        assert write_intent_lines == [], (
            "Expected no 'write-intent' line in direct mode, "
            f"got: {write_intent_lines}"
        )


def _make_run_with_workflow_transitions(output_dir: Path, transitions: list[dict]) -> None:
    """Complete run with workflow_transition events in audit trail."""
    import json
    _make_complete_run(output_dir)
    from src.run_paths import RunPaths
    paths = RunPaths.for_output_dir(output_dir)
    lines = [json.dumps({"event": "run_started"})]
    for t in transitions:
        lines.append(json.dumps(t))
    _write_file(paths.audit_trail, "\n".join(lines) + "\n")


class TestDoctorOutputWorkflowState:
    """Step 5: doctor output surfaces workflow state from audit trail."""

    def test_contains_workflow_state_section(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "hypothesis"},
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "hypothesis", "to_state": "converged"},
        ])
        result = doctor_output_text(tmp_path)
        assert "WORKFLOW" in result.text

    def test_shows_last_workflow_phase(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "execute"},
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "execute", "to_state": "converged"},
        ])
        result = doctor_output_text(tmp_path)
        assert "converged" in result.text

    def test_terminal_state_shown_as_terminal(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "converged"},
        ])
        result = doctor_output_text(tmp_path)
        assert "terminal" in result.text.lower() or "converged" in result.text

    def test_interrupted_state_shown(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "execute", "to_state": "interrupted"},
        ])
        result = doctor_output_text(tmp_path)
        assert "interrupted" in result.text

    def test_pause_state_shows_pending_gate(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "refine",
             "from_state": "verifier", "to_state": "paused_for_human"},
        ])
        result = doctor_output_text(tmp_path)
        assert "human" in result.text.lower() or "gate" in result.text.lower() or "pending" in result.text.lower()

    def test_no_workflow_transitions_shows_no_history(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)  # audit trail has only run_started
        result = doctor_output_text(tmp_path)
        # Should not crash; may show "no workflow history" or omit the section
        assert result.text  # non-empty

    def test_workflow_name_shown(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "hypothesis"},
        ])
        result = doctor_output_text(tmp_path)
        assert "research" in result.text

    def test_active_phase_shows_recovery_mode(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "hypothesis"},
        ])
        result = doctor_output_text(tmp_path)
        # hypothesis has outer_loop_continue recovery
        assert "outer_loop_continue" in result.text or "recovery" in result.text.lower()

    def test_paused_for_human_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "refine",
             "from_state": "verifier", "to_state": "paused_for_human"},
        ])
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_interrupted_workflow_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "execute", "to_state": "interrupted"},
        ])
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_non_terminal_active_phase_on_complete_run_exits_1(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "execute"},
        ])
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 1

    def test_converged_complete_run_exits_0(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "idle", "to_state": "hypothesis"},
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "hypothesis", "to_state": "converged"},
        ])
        result = doctor_output_text(tmp_path)
        assert result.exit_code == 0

    def test_paused_for_human_health_shows_warnings(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "refine",
             "from_state": "verifier", "to_state": "paused_for_human"},
        ])
        result = doctor_output_text(tmp_path)
        assert "WARN" in result.text or "ERROR" in result.text

    def test_interrupted_health_shows_warnings(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_run_with_workflow_transitions(tmp_path, [
            {"event": "workflow_transition", "workflow": "research",
             "from_state": "execute", "to_state": "interrupted"},
        ])
        result = doctor_output_text(tmp_path)
        assert "WARN" in result.text or "ERROR" in result.text

    def test_no_workflow_history_does_not_add_issues(self, tmp_path):
        from src.doctor import doctor_output_text
        _make_complete_run(tmp_path)
        result = doctor_output_text(tmp_path)
        # no workflow transitions → should not add workflow-related warnings
        assert "paused" not in result.text.lower()
        assert "interrupted" not in result.text.lower()
