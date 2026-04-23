"""Helpers for evaluation artifact persistence."""

from __future__ import annotations

import json
from typing import Any

from .artifacts import evaluation_payload, should_write_evaluation


def write_evaluation_artifacts(
    researcher: Any,
    *,
    evidence_quality: dict[str, Any],
    rubric: dict[str, Any],
    benchmark_summary: dict[str, Any],
    reference_comparison: dict[str, Any],
    semantic_review: dict[str, Any],
    semantic_calibration: dict[str, Any],
) -> None:
    """Write optional evaluation/comparison artifacts for a run."""
    if not should_write_evaluation(researcher.config):
        return

    payload = evaluation_payload(
        benchmark_id=researcher.config.evaluation.benchmark_id,
        baseline_exists=researcher.baseline_path.exists(),
        claims=researcher._claims,
        citations=researcher._citations,
        evidence_quality=evidence_quality,
        rubric=rubric,
        benchmark_summary=benchmark_summary,
        reference_comparison=reference_comparison,
        semantic_review=semantic_review,
        semantic_calibration=semantic_calibration,
    )
    researcher.evaluation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    researcher.comparison_path.write_text(json.dumps(reference_comparison, indent=2), encoding="utf-8")
    researcher.strategy_summary_path.write_text(
        json.dumps(reference_comparison.get("strategy_summary", {}), indent=2),
        encoding="utf-8",
    )
