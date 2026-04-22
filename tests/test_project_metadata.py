"""Tests for project metadata and optional dependency declarations."""

from pathlib import Path


def test_bedrock_optional_dependency_group_declared():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[project.optional-dependencies]" in text
    assert "bedrock = [" in text
    assert '"boto3' in text or "'boto3" in text
