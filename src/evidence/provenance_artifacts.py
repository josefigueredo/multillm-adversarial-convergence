"""Persistence helpers for provenance-related artifacts."""

from __future__ import annotations

import json
from typing import Any

from src.run_paths import RunPaths


def write_provenance_artifacts_bundle(
    paths: RunPaths,
    *,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    bundle: dict[str, Any],
    semantic_review: dict[str, Any],
    semantic_calibration: dict[str, Any],
) -> None:
    """Persist computed provenance and evidence artifacts to disk."""
    paths.claims.write_text(json.dumps(claims, indent=2), encoding="utf-8")
    paths.citations.write_text(json.dumps(citations, indent=2), encoding="utf-8")
    paths.evidence_links.write_text(json.dumps(bundle["evidence_links"], indent=2), encoding="utf-8")
    paths.search_log.write_text(json.dumps(bundle["search_log"], indent=2), encoding="utf-8")
    paths.screening_log.write_text(json.dumps(bundle["screening_log"], indent=2), encoding="utf-8")
    paths.evidence_quality.write_text(json.dumps(bundle["evidence_quality"], indent=2), encoding="utf-8")
    paths.rubric.write_text(json.dumps(bundle["rubric"], indent=2), encoding="utf-8")
    paths.contradictions.write_text(json.dumps(bundle["contradictions"], indent=2), encoding="utf-8")
    paths.certainty_tables.write_text(json.dumps(bundle["certainty_tables"], indent=2), encoding="utf-8")
    paths.semantic_review.write_text(json.dumps(semantic_review, indent=2), encoding="utf-8")
    paths.semantic_calibration.write_text(json.dumps(semantic_calibration, indent=2), encoding="utf-8")
