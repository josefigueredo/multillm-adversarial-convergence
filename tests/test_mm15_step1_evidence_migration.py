"""MM15 Step 1 — evidence Phase A: canonical module paths + shim backward compat."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical new-path imports (should work after files are moved)
# ---------------------------------------------------------------------------

class TestEvidenceCanonicalPaths:
    def test_references_module_importable_at_canonical_path(self):
        from src.evidence import references  # noqa: F401
        assert references is not None

    def test_provenance_module_importable_at_canonical_path(self):
        from src.evidence import provenance  # noqa: F401
        assert provenance is not None

    def test_provenance_artifacts_module_importable_at_canonical_path(self):
        from src.evidence import provenance_artifacts  # noqa: F401
        assert provenance_artifacts is not None

    def test_provenance_pipeline_module_importable_at_canonical_path(self):
        from src.evidence import provenance_pipeline  # noqa: F401
        assert provenance_pipeline is not None

    def test_build_references_section_from_evidence_references(self):
        from src.evidence.references import build_references_section
        assert callable(build_references_section)

    def test_extract_references_section_from_evidence_references(self):
        from src.evidence.references import extract_references_section
        result = extract_references_section("## References\n\n1. foo\n")
        assert "foo" in result

    def test_refs_heading_re_from_evidence_references(self):
        from src.evidence.references import REFS_HEADING_RE
        assert REFS_HEADING_RE.search("## References")

    def test_extract_citations_from_evidence_provenance(self):
        from src.evidence.provenance import extract_citations
        assert callable(extract_citations)

    def test_extract_claims_from_evidence_provenance(self):
        from src.evidence.provenance import extract_claims
        assert callable(extract_claims)

    def test_score_evidence_quality_from_evidence_provenance(self):
        from src.evidence.provenance import score_evidence_quality
        assert callable(score_evidence_quality)

    def test_score_research_rubric_from_evidence_provenance(self):
        from src.evidence.provenance import score_research_rubric
        assert callable(score_research_rubric)

    def test_write_provenance_artifacts_bundle_from_provenance_artifacts(self):
        from src.evidence.provenance_artifacts import write_provenance_artifacts_bundle
        assert callable(write_provenance_artifacts_bundle)

    def test_build_provenance_bundle_from_provenance_pipeline(self):
        from src.evidence.provenance_pipeline import build_provenance_bundle
        assert callable(build_provenance_bundle)


# ---------------------------------------------------------------------------
# Old flat-path imports must still work via compatibility shims
# ---------------------------------------------------------------------------

class TestEvidenceShimBackwardCompat:
    def test_build_references_section_still_importable_from_src_references(self):
        from src.references import build_references_section
        assert callable(build_references_section)

    def test_refs_heading_re_still_importable_from_src_references(self):
        from src.references import REFS_HEADING_RE
        assert REFS_HEADING_RE.search("## References")

    def test_extract_citations_still_importable_from_src_provenance(self):
        from src.provenance import extract_citations
        assert callable(extract_citations)

    def test_score_evidence_quality_still_importable_from_src_provenance(self):
        from src.provenance import score_evidence_quality
        assert callable(score_evidence_quality)

    def test_write_provenance_artifacts_bundle_from_src_provenance_artifacts(self):
        from src.provenance_artifacts import write_provenance_artifacts_bundle
        assert callable(write_provenance_artifacts_bundle)

    def test_build_provenance_bundle_from_src_provenance_pipeline(self):
        from src.provenance_pipeline import build_provenance_bundle
        assert callable(build_provenance_bundle)


# ---------------------------------------------------------------------------
# Regression: existing evidence package __init__ API still intact
# ---------------------------------------------------------------------------

class TestEvidencePackageApiUnchanged:
    def test_build_references_section_via_evidence_init(self):
        from src.evidence import build_references_section
        assert callable(build_references_section)

    def test_extract_citations_via_evidence_init(self):
        from src.evidence import extract_citations
        assert callable(extract_citations)

    def test_write_provenance_artifacts_bundle_via_evidence_init(self):
        from src.evidence import write_provenance_artifacts_bundle
        assert callable(write_provenance_artifacts_bundle)
