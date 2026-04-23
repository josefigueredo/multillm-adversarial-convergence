"""Helpers for reproducibility artifact writing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import prompt_snapshot_payload, rerun_script_text


def write_prompt_snapshot(path: Path, *, prompts: list[dict[str, Any]]) -> None:
    """Write the prompt snapshot artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = prompt_snapshot_payload(prompts=prompts)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_rerun_script(path: Path, *, config_path: Path | None, output_dir: Path) -> None:
    """Write a runnable shell script that replays the run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    script = rerun_script_text(config_path=config_path, output_dir=output_dir)
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
