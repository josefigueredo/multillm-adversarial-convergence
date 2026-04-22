"""Tests for provenance pipeline extraction."""

from src.provenance_pipeline import build_provenance_bundle


def test_build_provenance_bundle_computes_expected_artifacts():
    claims = [
        {
            "id": "synthesis-claim-001",
            "scope": "synthesis",
            "dimension": "DX",
            "text": "Python has strong docs. High confidence. https://docs.python.org/3/",
            "claim_type": "factual",
            "confidence": "high",
            "cited_urls": ["https://docs.python.org/3/"],
        }
    ]
    citations = [
        {
            "id": "synthesis-cite-001",
            "scope": "synthesis",
            "title": "Python docs",
            "url": "https://docs.python.org/3/",
            "source_type": "official_docs",
            "source_quality_weight": 1.0,
            "retrieved_at": "2026-04-22T00:00:00Z",
        }
    ]

    bundle = build_provenance_bundle(claims=claims, citations=citations)

    assert bundle["search_log"]["summary"]["sources_considered"] == 1
    assert bundle["screening_log"]["summary"]["included_count"] == 1
    assert bundle["rubric"]["summary"]["synthesis_claim_count"] == 1
    assert bundle["certainty_tables"]["summary"]["conclusions_count"] == 1
    assert bundle["semantic_review"]["enabled"] in {True, False}
