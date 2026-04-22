"""Tests for PRISMA-like search and screening log helpers."""

from src.research_logs import build_screening_log, build_search_log


def test_build_search_log_preserves_citation_retrieval_metadata():
    citations = [
        {
            "id": "cite-001",
            "scope": "synthesis",
            "title": "Python docs",
            "url": "https://docs.python.org/3/",
            "source_type": "official_docs",
            "retrieved_at": "2026-04-22T00:00:00Z",
        }
    ]

    log = build_search_log(citations)

    assert log["summary"]["queries_count"] == 1
    assert log["summary"]["sources_considered"] == 1
    assert log["entries"][0]["citation_id"] == "cite-001"
    assert log["entries"][0]["decision"] == "considered"


def test_build_screening_log_marks_linked_sources_as_included_and_unlinked_as_excluded():
    citations = [
        {
            "id": "cite-001",
            "scope": "synthesis",
            "title": "Python docs",
            "url": "https://docs.python.org/3/",
            "source_type": "official_docs",
            "retrieved_at": "2026-04-22T00:00:00Z",
        },
        {
            "id": "cite-002",
            "scope": "synthesis",
            "title": "Blog",
            "url": "https://example.com/blog",
            "source_type": "web",
            "retrieved_at": "2026-04-22T00:00:00Z",
        },
    ]
    evidence_links = [
        {
            "claim_id": "claim-001",
            "citation_ids": ["cite-001"],
            "support_strength": "strong",
        }
    ]

    log = build_screening_log(citations, evidence_links)

    assert log["summary"]["included_count"] == 1
    assert log["summary"]["excluded_count"] == 1
    included = next(item for item in log["entries"] if item["citation_id"] == "cite-001")
    excluded = next(item for item in log["entries"] if item["citation_id"] == "cite-002")
    assert included["decision"] == "included"
    assert included["reason"] == "linked_to_claims"
    assert included["linked_claim_ids"] == ["claim-001"]
    assert excluded["decision"] == "excluded"
    assert excluded["reason"] == "no_claim_links"
