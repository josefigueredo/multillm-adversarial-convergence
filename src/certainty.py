"""Conclusion-level certainty table helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


_DOWNGRADE_POINTS = {
    "not_serious": 0,
    "serious": 1,
    "very_serious": 2,
}


def build_certainty_tables(
    *,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    evidence_links: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build first-pass certainty tables for synthesis conclusions."""
    synthesis_claims = [claim for claim in claims if claim.get("scope") == "synthesis"]
    if not synthesis_claims:
        return {
            "summary": {
                "conclusions_count": 0,
                "certainty_counts": {},
            },
            "conclusions": [],
        }

    claims_by_dimension: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in synthesis_claims:
        dimension = str(claim.get("dimension") or "overall")
        claims_by_dimension[dimension].append(claim)

    links_by_claim = {str(link.get("claim_id", "")): link for link in evidence_links}
    citations_by_id = {str(citation.get("id", "")): citation for citation in citations}
    contradiction_pairs = {
        (str(item.get("left_claim_id", "")), str(item.get("right_claim_id", "")))
        for item in contradictions
    }

    conclusions: list[dict[str, Any]] = []
    certainty_counts: Counter[str] = Counter()

    for dimension, group in sorted(claims_by_dimension.items()):
        claim_ids = [str(claim.get("id", "")) for claim in group]
        group_links = [links_by_claim[claim_id] for claim_id in claim_ids if claim_id in links_by_claim]
        citation_ids = sorted(
            {
                str(citation_id)
                for link in group_links
                for citation_id in link.get("citation_ids", [])
                if citation_id
            }
        )
        group_citations = [citations_by_id[citation_id] for citation_id in citation_ids if citation_id in citations_by_id]
        contradiction_count = sum(
            1
            for left, right in contradiction_pairs
            if left in claim_ids or right in claim_ids
        )

        factors = {
            "risk_of_bias": _risk_of_bias_factor(group_links),
            "inconsistency": _inconsistency_factor(contradiction_count),
            "indirectness": _indirectness_factor(group),
            "imprecision": _imprecision_factor(group),
            "publication_bias": _publication_bias_factor(group_citations),
        }
        downgrade_points = sum(_DOWNGRADE_POINTS[factor["level"]] for factor in factors.values())
        certainty = _certainty_label(downgrade_points)
        certainty_counts[certainty] += 1

        conclusions.append(
            {
                "dimension": dimension,
                "certainty": certainty,
                "downgrade_points": downgrade_points,
                "claim_ids": claim_ids,
                "claim_count": len(group),
                "citation_count": len(group_citations),
                "factors": factors,
            }
        )

    return {
        "summary": {
            "conclusions_count": len(conclusions),
            "certainty_counts": dict(certainty_counts),
        },
        "conclusions": conclusions,
    }


def _risk_of_bias_factor(group_links: list[dict[str, Any]]) -> dict[str, str]:
    if not group_links:
        return {
            "level": "very_serious",
            "reason": "No linked evidence was found for this conclusion.",
        }
    avg_quality = sum(float(link.get("evidence_quality_score", 0.0)) for link in group_links) / len(group_links)
    if avg_quality >= 0.75:
        level = "not_serious"
    elif avg_quality >= 0.5:
        level = "serious"
    else:
        level = "very_serious"
    return {
        "level": level,
        "reason": f"Average evidence quality score was {avg_quality:.2f}.",
    }


def _inconsistency_factor(contradiction_count: int) -> dict[str, str]:
    if contradiction_count <= 0:
        level = "not_serious"
    elif contradiction_count == 1:
        level = "serious"
    else:
        level = "very_serious"
    return {
        "level": level,
        "reason": f"{contradiction_count} contradiction(s) were detected for this conclusion.",
    }


def _indirectness_factor(group_claims: list[dict[str, Any]]) -> dict[str, str]:
    interpretive_count = sum(
        1 for claim in group_claims if str(claim.get("claim_type", "")) in {"recommendation", "interpretive"}
    )
    ratio = interpretive_count / len(group_claims) if group_claims else 1.0
    if ratio <= 0.34:
        level = "not_serious"
    elif ratio <= 0.67:
        level = "serious"
    else:
        level = "very_serious"
    return {
        "level": level,
        "reason": f"{interpretive_count} of {len(group_claims)} claim(s) are interpretive or recommendation-oriented.",
    }


def _imprecision_factor(group_claims: list[dict[str, Any]]) -> dict[str, str]:
    uncertain = sum(
        1 for claim in group_claims if str(claim.get("confidence", "")) in {"low", "unresolved", "unlabeled"}
    )
    ratio = uncertain / len(group_claims) if group_claims else 1.0
    if ratio <= 0.2:
        level = "not_serious"
    elif ratio <= 0.5:
        level = "serious"
    else:
        level = "very_serious"
    return {
        "level": level,
        "reason": f"{uncertain} of {len(group_claims)} claim(s) have low, unresolved, or unlabeled confidence.",
    }


def _publication_bias_factor(group_citations: list[dict[str, Any]]) -> dict[str, str]:
    source_types = {str(citation.get("source_type", "")) for citation in group_citations if citation.get("source_type")}
    if len(source_types) >= 2:
        level = "not_serious"
    elif len(source_types) == 1:
        level = "serious"
    else:
        level = "very_serious"
    return {
        "level": level,
        "reason": f"Evidence spans {len(source_types)} distinct source type(s).",
    }


def _certainty_label(downgrade_points: int) -> str:
    if downgrade_points <= 0:
        return "high"
    if downgrade_points == 1:
        return "moderate"
    if downgrade_points == 2:
        return "low"
    return "very_low"
