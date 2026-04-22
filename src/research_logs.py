"""PRISMA-like search and screening log helpers."""

from __future__ import annotations

from typing import Any


def build_search_log(citations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a simple search log from collected citations."""
    entries = [
        {
            "citation_id": citation.get("id", ""),
            "scope": citation.get("scope", ""),
            "title": citation.get("title", ""),
            "url": citation.get("url", ""),
            "source_type": citation.get("source_type", ""),
            "retrieved_at": citation.get("retrieved_at", ""),
            "decision": "considered",
        }
        for citation in citations
    ]
    return {
        "summary": {
            "queries_count": len(entries),
            "sources_considered": len(entries),
        },
        "entries": entries,
    }


def build_screening_log(
    citations: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a source-screening log from citations and linked claims."""
    links_by_citation: dict[str, list[dict[str, Any]]] = {}
    for link in evidence_links:
        if not isinstance(link, dict):
            continue
        for citation_id in link.get("citation_ids", []):
            links_by_citation.setdefault(str(citation_id), []).append(link)

    entries: list[dict[str, Any]] = []
    included = 0
    excluded = 0
    for citation in citations:
        citation_id = str(citation.get("id", ""))
        linked = links_by_citation.get(citation_id, [])
        decision = "included" if linked else "excluded"
        reason = "linked_to_claims" if linked else "no_claim_links"
        if linked:
            included += 1
        else:
            excluded += 1
        entries.append(
            {
                "citation_id": citation_id,
                "scope": citation.get("scope", ""),
                "title": citation.get("title", ""),
                "url": citation.get("url", ""),
                "source_type": citation.get("source_type", ""),
                "retrieved_at": citation.get("retrieved_at", ""),
                "decision": decision,
                "reason": reason,
                "linked_claim_ids": [str(item.get("claim_id", "")) for item in linked if item.get("claim_id")],
                "support_strengths": [
                    str(item.get("support_strength", ""))
                    for item in linked
                    if item.get("support_strength")
                ],
            }
        )
    return {
        "summary": {
            "sources_screened": len(entries),
            "included_count": included,
            "excluded_count": excluded,
        },
        "entries": entries,
    }
