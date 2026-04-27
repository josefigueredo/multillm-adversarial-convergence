"""Evidence domain package — MM12 Step 2 / MM15 Step 1.

Re-exports the public API for research evidence — deterministic references,
provenance tracking, and claim/citation extraction — under a single package
boundary.  Existing flat-module imports (``from src.references import …``)
remain valid via compatibility shims.

Contexts exposed:
- References: heading regex, deduplication, building, injection, extraction
- Provenance: claims, citations, scoring, artifact bundle writing
"""

from __future__ import annotations

# ── References ────────────────────────────────────────────────────────────────
from .references import (
    REFS_HEADING_RE,
    build_references_section,
    dedupe_citations,
    extract_references_section,
    generate_references_for_synthesis,
    inject_references_section,
    normalize_url,
)

# ── Provenance ────────────────────────────────────────────────────────────────
from .provenance import (
    build_source_file_provenance,
    detect_claim_conflicts,
    extract_citations,
    extract_claims,
    link_claims_to_citations,
    score_evidence_quality,
    score_research_rubric,
    summarize_evidence_quality,
)
from .provenance_artifacts import write_provenance_artifacts_bundle

__all__ = [
    # references
    "REFS_HEADING_RE",
    "normalize_url",
    "dedupe_citations",
    "build_references_section",
    "inject_references_section",
    "extract_references_section",
    "generate_references_for_synthesis",
    # provenance
    "build_source_file_provenance",
    "detect_claim_conflicts",
    "extract_citations",
    "extract_claims",
    "link_claims_to_citations",
    "score_evidence_quality",
    "score_research_rubric",
    "summarize_evidence_quality",
    "write_provenance_artifacts_bundle",
]
