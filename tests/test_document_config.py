from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import pytest

from src.config import ArtifactConfig, DocumentConfig, PersonaConfig, SourceFileConfig


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


def test_source_file_config_glob_expansion(tmp_path):
    (tmp_path / "a.md").write_text("A")
    (tmp_path / "b.md").write_text("B")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "*.md"
              roles: [builder]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 2
    assert all(sf.roles == ("builder",) for sf in cfg.source_files)
    paths = {sf.path for sf in cfg.source_files}
    assert str(tmp_path / "a.md") in paths
    assert str(tmp_path / "b.md") in paths


def test_source_file_config_literal_path_not_found_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "nonexistent.md"
              roles: [builder]
    """)
    with pytest.raises(ValueError, match="nonexistent.md"):
        DocumentConfig.from_yaml(cfg_path)


def test_source_file_config_all_role_expands(tmp_path):
    (tmp_path / "file.md").write_text("content")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          personas:
            - name: architect
            - name: scrum_master
          source_files:
            - path: "file.md"
              roles: [all]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    roles = set(cfg.source_files[0].roles)
    assert "builder" in roles
    assert "challenger" in roles
    assert "architect" in roles
    assert "scrum_master" in roles


def test_source_file_config_empty_glob_warns_and_skips(tmp_path, caplog):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "*.nonexistent"
              roles: [builder]
    """)
    with caplog.at_level(logging.WARNING):
        cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 0
    assert "*.nonexistent" in caplog.text


def test_source_file_config_absolute_path(tmp_path):
    f = tmp_path / "abs.md"
    f.write_text("content")
    cfg_path = _write_yaml(tmp_path, f"""
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "{f}"
              roles: [builder]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    assert cfg.source_files[0].path == str(f)
    assert cfg.source_files[0].roles == ("builder",)


def test_source_file_config_empty_when_not_declared(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.source_files == ()


def test_source_file_config_multiple_roles(tmp_path):
    f = tmp_path / "file.md"
    f.write_text("content")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "file.md"
              roles: [builder, architect]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert set(cfg.source_files[0].roles) == {"builder", "architect"}


def test_source_file_config_absolute_glob(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.md").write_text("A")
    (sub / "b.md").write_text("B")
    # Use absolute glob pattern
    pattern = str(sub / "*.md")
    cfg_path = _write_yaml(tmp_path, f"""
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "{pattern}"
              roles: [builder]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 2
    paths = {sf.path for sf in cfg.source_files}
    assert str(sub / "a.md") in paths
    assert str(sub / "b.md") in paths
