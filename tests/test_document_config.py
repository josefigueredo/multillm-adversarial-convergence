from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config import ArtifactConfig, DocumentConfig, PersonaConfig


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_document_config_minimal(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "My PRD"
          goal: "Build it"
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.topic == "My PRD"
    assert cfg.goal == "Build it"
    assert cfg.primary_artifact == "PRD.md"
    assert cfg.convergence_cycles == 1
    assert cfg.max_cycles == 0
    assert cfg.persona_mode == "parallel"
    assert len(cfg.personas) == 3


def test_document_config_full(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "Iris PRD"
          goal: "Execution-ready PRD"
          primary_artifact: "SPEC.md"
          convergence_cycles: 2
          max_cycles: 10
          persona_mode: serial
          personas:
            - name: architect
            - name: product_owner
          artifacts:
            - name: V1_SLICE.md
              layer: execution
              review: true
            - name: ARCH.md
              layer: companion
              review: false
          backends:
            primary: claude
            research: [codex, claude]
            judge: gemini
            utility: claude
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.primary_artifact == "SPEC.md"
    assert cfg.convergence_cycles == 2
    assert cfg.max_cycles == 10
    assert cfg.persona_mode == "serial"
    assert len(cfg.personas) == 2
    assert cfg.personas[0].name == "architect"
    assert len(cfg.artifacts) == 2
    assert cfg.artifacts[0].layer == "execution"
    assert cfg.artifacts[1].review is False
    assert cfg.backends.primary == "claude"
    assert cfg.backends.research == ("codex", "claude")
    assert cfg.backends.judge == "gemini"


def test_document_config_missing_topic_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          goal: "No topic"
    """)
    with pytest.raises(ValueError, match="topic"):
        DocumentConfig.from_yaml(cfg_path)


def test_document_config_missing_document_key_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        research:
          topic: "Wrong key"
          goal: "x"
          dimensions: []
    """)
    with pytest.raises(ValueError, match="document"):
        DocumentConfig.from_yaml(cfg_path)


def test_document_config_invalid_persona_mode_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          persona_mode: diagonal
    """)
    with pytest.raises(ValueError, match="persona_mode"):
        DocumentConfig.from_yaml(cfg_path)


def test_persona_config_default_prompt_file():
    p = PersonaConfig(name="architect")
    assert p.prompt_file == ""


def test_artifact_config_defaults():
    a = ArtifactConfig(name="V1.md", layer="execution")
    assert a.review is True
    assert a.prompt_file == ""
