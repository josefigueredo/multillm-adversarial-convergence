"""Tests for certainty-table generation."""

from src.certainty import build_certainty_tables


def test_build_certainty_tables_high_evidence_conclusion():
    claims = [
        {
            "id": "synthesis-claim-001",
            "scope": "synthesis",
            "dimension": "DX",
            "text": "Python packaging docs are comprehensive. High confidence.",
            "claim_type": "factual",
            "confidence": "high",
        }
    ]
    citations = [
        {
            "id": "synthesis-cite-001",
            "scope": "synthesis",
            "source_type": "official_docs",
            "url": "https://packaging.python.org/",
        },
        {
            "id": "synthesis-cite-002",
            "scope": "synthesis",
            "source_type": "repository",
            "url": "https://github.com/pypa/packaging.python.org",
        },
    ]
    evidence_links = [
        {
            "claim_id": "synthesis-claim-001",
            "citation_ids": ["synthesis-cite-001", "synthesis-cite-002"],
            "support_strength": "strong",
            "evidence_quality_score": 0.91,
        }
    ]

    payload = build_certainty_tables(
        claims=claims,
        citations=citations,
        evidence_links=evidence_links,
        contradictions=[],
    )

    assert payload["summary"]["conclusions_count"] == 1
    assert payload["summary"]["certainty_counts"]["high"] == 1
    assert payload["summary"]["high_certainty_factual_count"] == 1
    assert payload["summary"]["high_certainty_recommendation_count"] == 0
    conclusion = payload["conclusions"][0]
    assert conclusion["dimension"] == "DX"
    assert conclusion["certainty"] == "high"
    assert conclusion["factors"]["risk_of_bias"]["level"] == "not_serious"
    assert conclusion["factors"]["publication_bias"]["level"] == "not_serious"


def test_build_certainty_tables_downgrades_contradictory_sparse_conclusion():
    claims = [
        {
            "id": "synthesis-claim-001",
            "scope": "synthesis",
            "dimension": "Runtime",
            "text": "Use tool A for production migrations.",
            "claim_type": "recommendation",
            "confidence": "low",
        },
        {
            "id": "synthesis-claim-002",
            "scope": "synthesis",
            "dimension": "Runtime",
            "text": "Avoid tool A for production migrations.",
            "claim_type": "recommendation",
            "confidence": "unresolved",
        },
    ]
    citations = [
        {
            "id": "synthesis-cite-001",
            "scope": "synthesis",
            "source_type": "web",
            "url": "https://example.com/blog",
        }
    ]
    evidence_links = [
        {
            "claim_id": "synthesis-claim-001",
            "citation_ids": ["synthesis-cite-001"],
            "support_strength": "weak",
            "evidence_quality_score": 0.28,
        },
        {
            "claim_id": "synthesis-claim-002",
            "citation_ids": [],
            "support_strength": "weak",
            "evidence_quality_score": 0.10,
        },
    ]
    contradictions = [
        {
            "left_claim_id": "synthesis-claim-001",
            "right_claim_id": "synthesis-claim-002",
            "reason": "opposing recommendations about similar object",
        }
    ]

    payload = build_certainty_tables(
        claims=claims,
        citations=citations,
        evidence_links=evidence_links,
        contradictions=contradictions,
    )

    assert payload["summary"]["high_certainty_recommendation_count"] == 0
    conclusion = payload["conclusions"][0]
    assert conclusion["certainty"] == "very_low"
    assert conclusion["factors"]["risk_of_bias"]["level"] == "very_serious"
    assert conclusion["factors"]["inconsistency"]["level"] == "serious"
    assert conclusion["factors"]["publication_bias"]["level"] == "serious"
