"""Unit tests for src.explain."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import (
    BackendsConfig,
    EvaluationConfig,
    ExecutionConfig,
    ReportingConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)
from src.explain import explain_config_text


def _make_config(**kwargs) -> ResearchConfig:
    defaults = dict(
        topic="Compare API gateways",
        goal="Architect-level decision",
        dimensions=("REST vs HTTP", "Auth options"),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            strategy="ensemble",
            backends=BackendsConfig(
                primary="claude-cli",
                research=["claude-cli", "codex-cli"],
            ),
        ),
        security=SecurityConfig(
            content_trust="permissive",
            tool_execution_mode="sandboxed",
            sandbox=SandboxConfig(
                mode="tool_calls",
                network_access="web_only",
            ),
        ),
    )
    defaults.update(kwargs)
    return ResearchConfig(**defaults)


class TestExplainConfigText:
    def test_returns_nonempty_string(self):
        result = explain_config_text(_make_config())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_topic_and_goal(self):
        result = explain_config_text(_make_config())
        assert "Compare API gateways" in result
        assert "Architect-level decision" in result

    def test_contains_dimensions(self):
        result = explain_config_text(_make_config())
        assert "REST vs HTTP" in result
        assert "Auth options" in result

    def test_contains_strategy(self):
        result = explain_config_text(_make_config())
        assert "ensemble" in result

    def test_contains_backend_role_mapping(self):
        result = explain_config_text(_make_config())
        assert "claude-cli" in result
        assert "codex-cli" in result

    def test_contains_security_policy_section(self):
        result = explain_config_text(_make_config())
        assert "SECURITY POLICY" in result

    def test_contains_content_trust(self):
        result = explain_config_text(_make_config())
        assert "permissive" in result

    def test_contains_tool_execution_mode(self):
        result = explain_config_text(_make_config())
        assert "sandboxed" in result

    def test_contains_sandbox_mode(self):
        result = explain_config_text(_make_config())
        assert "tool_calls" in result

    def test_contains_sandbox_network(self):
        result = explain_config_text(_make_config())
        assert "web_only" in result

    def test_contains_output_style(self):
        result = explain_config_text(
            _make_config(reporting=ReportingConfig(output_style="paper"))
        )
        assert "paper" in result

    def test_contains_artifacts_section(self):
        result = explain_config_text(_make_config())
        assert "ARTIFACTS" in result
        assert "effective_config" in result
        assert "manifest" in result

    def test_config_path_shown_when_provided(self, tmp_path: Path):
        cfg_path = tmp_path / "my_research.yaml"
        result = explain_config_text(_make_config(), config_path=cfg_path)
        assert "my_research" in result

    def test_no_dims_shows_none_configured(self):
        result = explain_config_text(_make_config(dimensions=()))
        assert "none configured" in result

    def test_providers_section_shown_when_present(self):
        cfg = _make_config()
        result = explain_config_text(cfg)
        if cfg.providers:
            assert "PROVIDERS" in result

    def test_does_not_create_output_dirs(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        explain_config_text(_make_config())
        assert not any(tmp_path.iterdir())
