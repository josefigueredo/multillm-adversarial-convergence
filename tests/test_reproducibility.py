"""Tests for reproducibility artifact helpers."""

import json
from pathlib import Path

from src.reproducibility import write_prompt_snapshot, write_rerun_script


def test_write_prompt_snapshot_writes_payload(tmp_path: Path):
    path = tmp_path / "prompt_snapshot.json"

    write_prompt_snapshot(
        path,
        prompts=[
            {
                "backend": "codex-api",
                "model": "gpt-5.4",
                "prompt": "Investigate Python packaging.",
            }
        ],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["entries_count"] == 1
    assert payload["entries"][0]["backend"] == "codex-api"
    assert payload["entries"][0]["prompt_sha256"]


def test_write_rerun_script_writes_executable_script(tmp_path: Path):
    path = tmp_path / "rerun.sh"

    write_rerun_script(
        path,
        config_path=tmp_path / "config.yaml",
        output_dir=tmp_path / "out",
    )

    content = path.read_text(encoding="utf-8")
    assert path.exists()
    assert content.startswith("#!/usr/bin/env bash")
    assert "autoresearch research" in content
