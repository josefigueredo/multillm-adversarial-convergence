"""Tests for structured execution audit trail logging."""

from __future__ import annotations

import json
from pathlib import Path

from src.audit_trail import AuditTrailWriter


def _read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_audit_trail_emits_started_completed_and_file_events(tmp_path: Path):
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    writer = AuditTrailWriter(output_dir / "audit_trail.jsonl", mode="run", run_id="run-a")

    with writer.step("setup_run", artifact_root=output_dir):
        (output_dir / "methods.md").write_text("# Methods\n", encoding="utf-8")

    events = _read_events(output_dir / "audit_trail.jsonl")
    assert events[0]["event"] == "step_started"
    assert events[0]["step"] == "setup_run"
    assert any(event["event"] == "file_written" and event["path"] == "methods.md" for event in events)
    assert events[-1]["event"] == "step_completed"
    assert events[-1]["created_files"] == ["methods.md"]


def test_audit_trail_ignores_its_own_log_files_in_diffs(tmp_path: Path):
    output_dir = tmp_path / "run"
    output_dir.mkdir()
    writer = AuditTrailWriter(output_dir / "audit_trail.jsonl", mode="run", run_id="run-b")
    (output_dir / "run.log").write_text("seed\n", encoding="utf-8")

    with writer.step("noop", artifact_root=output_dir):
        pass

    events = _read_events(output_dir / "audit_trail.jsonl")
    completed = events[-1]
    assert completed["event"] == "step_completed"
    assert completed["created_files"] == []
    assert completed["updated_files"] == []
