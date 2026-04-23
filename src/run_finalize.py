"""Run finalization orchestration helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def finalize_run_artifacts(researcher: object) -> None:
    """Execute final artifact-writing steps for a completed run."""
    researcher._run_completed_at = datetime.now(timezone.utc).isoformat()
    researcher._write_run_metadata_artifacts()
    researcher._write_prompt_snapshot_artifact()
    researcher._write_agreement_artifact()
    researcher._write_provenance_artifacts()
    researcher._write_reporting_artifacts()
