"""Computed provenance/evidence bundle helpers."""

from __future__ import annotations

from typing import Any

from .certainty import build_certainty_tables
from .provenance import (
    detect_claim_conflicts,
    link_claims_to_citations,
    score_research_rubric,
    summarize_evidence_quality,
)
from .research_logs import build_screening_log, build_search_log
from .semantic_eval import semantic_calibration, semantic_review_disabled


def build_provenance_bundle(
    *,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    benchmark_summary: dict[str, Any] | None = None,
    reference_comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the core provenance/evaluation bundle from claims and citations."""
    evidence_links = link_claims_to_citations(claims, citations)
    search_log = build_search_log(citations)
    screening_log = build_screening_log(citations, evidence_links)
    evidence_quality = summarize_evidence_quality(claims, evidence_links)
    contradictions = detect_claim_conflicts(claims)
    rubric = score_research_rubric(
        claims,
        citations,
        evidence_links,
        contradictions,
    )
    certainty_tables = build_certainty_tables(
        claims=claims,
        citations=citations,
        evidence_links=evidence_links,
        contradictions=contradictions,
    )
    benchmark = benchmark_summary or {}
    comparison = reference_comparison or {}
    return {
        "evidence_links": evidence_links,
        "search_log": search_log,
        "screening_log": screening_log,
        "evidence_quality": evidence_quality,
        "contradictions": contradictions,
        "rubric": rubric,
        "certainty_tables": certainty_tables,
        "semantic_review": semantic_review_disabled(),
        "semantic_calibration": semantic_calibration(
            enabled=False,
            goal="",
            methodology_question="",
            methodology_scope="",
            rubric=rubric,
            evidence_quality=evidence_quality,
            benchmark_summary=benchmark,
            reference_comparison=comparison,
        ),
    }
