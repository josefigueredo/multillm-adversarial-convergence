from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config import ArtifactConfig, PlanConfig, PlanPersonaConfig, ProviderConfig, SourceFileConfig


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_plan_config_minimal(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "My Plan"
          goal: "Build it"
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.topic == "My Plan"
    assert cfg.goal == "Build it"
    assert cfg.primary_artifact == "PLAN.md"
    assert cfg.convergence_cycles == 2
    assert cfg.max_cycles == 10
    assert cfg.persona_mode == "parallel"
    assert len(cfg.personas) == 7
    assert cfg.personas[0].name == "architect"
    assert cfg.personas[6].name == "devils_advocate"


def test_plan_config_custom_personas(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          personas:
            - name: architect
            - name: security_engineer
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.personas) == 2
    assert cfg.personas[1].name == "security_engineer"


def test_plan_config_custom_artifact(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          primary_artifact: "MY_PLAN.md"
          convergence_cycles: 3
          max_cycles: 20
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.primary_artifact == "MY_PLAN.md"
    assert cfg.convergence_cycles == 3
    assert cfg.max_cycles == 20


def test_plan_config_artifacts(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          artifacts:
            - name: RISK_REGISTER.md
              layer: companion
              review: false
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.artifacts) == 1
    assert cfg.artifacts[0].name == "RISK_REGISTER.md"
    assert cfg.artifacts[0].review is False


def test_plan_config_backends(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          backends:
            primary: claude-cli
            research: [claude-cli, gemini-cli]
            judge: claude-cli
            utility: gemini-cli
          execution:
            model: opus
            allowed_tools: "Read,Bash"
            max_turns: 12
            timeout_seconds: 222
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.backends.primary == "claude-cli"
    assert cfg.backends.research == ("claude-cli", "gemini-cli")
    assert cfg.backends.judge == "claude-cli"
    assert cfg.backends.utility == "gemini-cli"
    assert cfg.execution.model == "opus"
    assert cfg.execution.allowed_tools == "Read,Bash"
    assert cfg.execution.max_turns == 12
    assert cfg.execution.timeout_seconds == 222


def test_plan_config_accepts_explicit_cli_aliases(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          backends:
            primary: claude-cli
            research: [claude-cli, gemini-cli]
            judge: claude-cli
            utility: gemini-cli
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.backends.primary == "claude-cli"
    assert cfg.backends.research == ("claude-cli", "gemini-cli")
    assert cfg.backends.judge == "claude-cli"
    assert cfg.backends.utility == "gemini-cli"


def test_plan_config_provider_instances_parse(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          providers:
            planner_main:
              adapter: claude-cli
              model: opus
            verifier_fast:
              adapter: gemini-cli
              model: gemini-2.5-flash
          backends:
            primary: planner_main
            research: [planner_main, verifier_fast]
            judge: planner_main
            utility: verifier_fast
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.providers["planner_main"] == ProviderConfig(adapter="claude-cli", model="opus")
    assert cfg.backends.primary == "planner_main"
    assert cfg.backends.research == ("planner_main", "verifier_fast")


def test_plan_config_provider_reference_must_exist(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          providers:
            planner_main:
              adapter: claude-cli
          backends:
            primary: missing
    """)
    with pytest.raises(ValueError, match="Unknown provider instance"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_missing_topic_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          goal: "No topic"
    """)
    with pytest.raises(ValueError, match="topic"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_missing_plan_key_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "wrong key"
    """)
    with pytest.raises(ValueError, match="plan"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_invalid_persona_mode_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          persona_mode: invalid
    """)
    with pytest.raises(ValueError, match="persona_mode"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_legacy_primary_backend_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          backends:
            primary: claude
    """)
    with pytest.raises(ValueError, match="Invalid primary backend"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_invalid_research_backend_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          backends:
            primary: claude-cli
            research: [claude-cli, nope]
    """)
    with pytest.raises(ValueError, match="Invalid research backend"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_source_files(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec")
    cfg_path = _write_yaml(tmp_path, f"""
        plan:
          topic: "T"
          goal: "G"
          source_files:
            - path: spec.md
              roles: [builder, architect]
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    assert cfg.source_files[0].roles == ("architect", "builder")


def test_plan_persona_config_default_prompt_file():
    p = PlanPersonaConfig(name="tech_lead")
    assert p.prompt_file == ""


def test_plan_persona_config_custom_prompt_file():
    p = PlanPersonaConfig(name="tech_lead", prompt_file="my_prompt.md")
    assert p.prompt_file == "my_prompt.md"
