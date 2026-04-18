from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config import ArtifactConfig, PlanConfig, PlanPersonaConfig, SourceFileConfig


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
            primary: claude
            research: [claude, gemini]
            judge: claude
            utility: gemini
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.backends.primary == "claude"
    assert cfg.backends.research == ("claude", "gemini")
    assert cfg.backends.judge == "claude"
    assert cfg.backends.utility == "gemini"


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
