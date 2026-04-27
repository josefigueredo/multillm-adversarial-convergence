"""MM16 Step 4 — workspace isolation line in doctor; sandbox.scope in explain."""

from __future__ import annotations

from src.config import (
    BackendsConfig,
    ExecutionConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)
from src.doctor import doctor_config_text
from src.explain import explain_config_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(sandbox: SandboxConfig | None = None) -> ResearchConfig:
    sec_kwargs: dict = {}
    if sandbox is not None:
        sec_kwargs["sandbox"] = sandbox
    return ResearchConfig(
        topic="Caching strategies",
        goal="Architecture decision",
        dimensions=("Latency", "Cost"),
        execution=ExecutionConfig(
            backend="claude-cli",
            backends=BackendsConfig(primary="claude-cli"),
            allowed_tools="WebSearch",
        ),
        scoring=ScoringConfig(),
        security=SecurityConfig(**sec_kwargs),
    )


# ---------------------------------------------------------------------------
# Doctor — workspace isolation line
# ---------------------------------------------------------------------------

class TestDoctorWorkspaceIsolationLine:
    def test_scope_run_shows_per_run_workspace_isolation(self):
        config = _make_config(SandboxConfig(scope="run"))
        text = doctor_config_text(config).text
        assert "workspace isolation: per-run" in text

    def test_scope_run_workspace_line_contains_shared_note(self):
        config = _make_config(SandboxConfig(scope="run"))
        text = doctor_config_text(config).text
        assert "shared across iterations" in text

    def test_scope_run_workspace_line_contains_path_hint(self):
        config = _make_config(SandboxConfig(scope="run"))
        text = doctor_config_text(config).text
        assert ".workspace/" in text

    def test_scope_iteration_shows_per_iteration_workspace_isolation(self):
        config = _make_config(SandboxConfig(scope="iteration"))
        text = doctor_config_text(config).text
        assert "workspace isolation: per-iteration" in text

    def test_scope_iteration_workspace_line_contains_iter_path(self):
        config = _make_config(SandboxConfig(scope="iteration"))
        text = doctor_config_text(config).text
        assert "iter_NNNN" in text

    def test_scope_iteration_workspace_line_contains_workspace_path(self):
        config = _make_config(SandboxConfig(scope="iteration"))
        text = doctor_config_text(config).text
        assert ".workspace/" in text

    def test_scope_run_does_not_mention_iter_nnnn(self):
        """scope=run should not show iter_NNNN in the workspace isolation line."""
        config = _make_config(SandboxConfig(scope="run"))
        text = doctor_config_text(config).text
        assert "iter_NNNN" not in text

    def test_scope_iteration_does_not_say_shared(self):
        """scope=iteration should not say 'shared across iterations'."""
        config = _make_config(SandboxConfig(scope="iteration"))
        text = doctor_config_text(config).text
        assert "shared across iterations" not in text

    def test_workspace_isolation_appears_in_enforcement_section(self):
        """The workspace isolation line should appear in the SECURITY ENFORCEMENT STATUS section."""
        config = _make_config(SandboxConfig(scope="iteration"))
        text = doctor_config_text(config).text
        enforcement_pos = text.index("SECURITY ENFORCEMENT STATUS")
        isolation_pos = text.index("workspace isolation:")
        # Should come after the section header and before the next section
        assert isolation_pos > enforcement_pos


# ---------------------------------------------------------------------------
# Explain — sandbox.scope already present
# ---------------------------------------------------------------------------

class TestExplainSandboxScope:
    def test_explain_shows_sandbox_scope_run(self):
        config = _make_config(SandboxConfig(scope="run"))
        text = explain_config_text(config)
        assert "sandbox.scope:" in text
        assert "run" in text

    def test_explain_shows_sandbox_scope_iteration(self):
        config = _make_config(SandboxConfig(scope="iteration"))
        text = explain_config_text(config)
        assert "sandbox.scope:" in text
        assert "iteration" in text
