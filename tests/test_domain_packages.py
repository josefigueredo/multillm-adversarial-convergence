"""TDD tests for MM12 Step 2 — domain package seams.

Verifies that:
1. src.deliverables exposes the full publication pipeline public API.
2. src.evidence exposes the references/provenance public API.
3. Original flat-module imports remain backward-compatible.

All tests fail before the __init__.py files are created.
"""

# ---------------------------------------------------------------------------
# src.deliverables — pipeline model
# ---------------------------------------------------------------------------

class TestDeliverablesPackagePipelineModel:
    def test_import_pipeline_stage(self):
        from src.deliverables import PipelineStage
        assert PipelineStage.PENDING

    def test_import_synthesis_artifact(self):
        from src.deliverables import SynthesisArtifact
        a = SynthesisArtifact(title="T", body="B")
        assert a.title == "T"

    def test_import_revision_artifact(self):
        from src.deliverables import RevisionArtifact
        assert RevisionArtifact(revised_body="x").revised_body == "x"

    def test_import_package_artifact(self):
        from src.deliverables import PackageArtifact
        assert PackageArtifact(format="latex").format == "latex"

    def test_import_export_artifact(self):
        from src.deliverables import ExportArtifact
        assert ExportArtifact().output_paths == ()

    def test_import_deliverable_pipeline(self):
        from src.deliverables import DeliverablePipeline
        p = DeliverablePipeline(topic="T")
        assert p.topic == "T"


# ---------------------------------------------------------------------------
# src.deliverables — class configs and factory
# ---------------------------------------------------------------------------

class TestDeliverablesPackageClasses:
    def test_import_deliverable_class(self):
        from src.deliverables import DeliverableClass
        assert DeliverableClass.PAPER

    def test_import_deliverable_class_config(self):
        from src.deliverables import DeliverableClassConfig
        assert DeliverableClassConfig

    def test_import_class_configs_registry(self):
        from src.deliverables import CLASS_CONFIGS, DeliverableClass
        assert DeliverableClass.PAPER in CLASS_CONFIGS

    def test_import_named_configs(self):
        from src.deliverables import (
            PAPER_CONFIG,
            TECHNICAL_DOC_CONFIG,
            EXECUTIVE_BRIEF_CONFIG,
            DECISION_MEMO_CONFIG,
        )
        assert PAPER_CONFIG.requires_citations is True
        assert EXECUTIVE_BRIEF_CONFIG.requires_citations is False

    def test_import_validate_synthesis_for_class(self):
        from src.deliverables import validate_synthesis_for_class, PAPER_CONFIG, SynthesisArtifact
        violations = validate_synthesis_for_class(
            SynthesisArtifact(title="T", body="abstract introduction methodology results conclusion"),
            PAPER_CONFIG,
        )
        assert isinstance(violations, list)

    def test_import_create_pipeline(self):
        from src.deliverables import create_pipeline, DeliverableClass
        p = create_pipeline("topic", DeliverableClass.PAPER)
        assert p.deliverable_class == "paper"

    def test_import_get_config_for_pipeline(self):
        from src.deliverables import get_config_for_pipeline, create_pipeline, DeliverableClass, PAPER_CONFIG
        p = create_pipeline("T", DeliverableClass.PAPER)
        assert get_config_for_pipeline(p) == PAPER_CONFIG


# ---------------------------------------------------------------------------
# src.deliverables — verification
# ---------------------------------------------------------------------------

class TestDeliverablesPackageVerification:
    def test_import_verification_violation(self):
        from src.deliverables import VerificationViolation
        v = VerificationViolation(code="c", message="m")
        assert v.code == "c"

    def test_import_verify_body_citations(self):
        from src.deliverables import verify_body_citations, PAPER_CONFIG
        assert callable(verify_body_citations)

    def test_import_verify_synthesis_citations(self):
        from src.deliverables import verify_synthesis_citations
        assert callable(verify_synthesis_citations)

    def test_import_verify_export_artifact(self):
        from src.deliverables import verify_export_artifact, ExportArtifact
        violations = verify_export_artifact(ExportArtifact(output_paths=(), exported_at=""))
        assert len(violations) > 0


# ---------------------------------------------------------------------------
# src.deliverables — export bundles
# ---------------------------------------------------------------------------

class TestDeliverablesPackageExportBundle:
    def test_import_bundle_manifest(self):
        from src.deliverables import BundleManifest
        m = BundleManifest(bundle_id="x", topic="T", deliverable_class=None, format="latex")
        assert m.bundle_id == "x"

    def test_import_bundle_provenance(self):
        from src.deliverables import BundleProvenance
        p = BundleProvenance(source_count=3, key_findings=("f",))
        assert p.source_count == 3

    def test_import_export_bundle(self):
        from src.deliverables import ExportBundle
        assert ExportBundle

    def test_import_build_export_bundle(self):
        from src.deliverables import build_export_bundle
        assert callable(build_export_bundle)


# ---------------------------------------------------------------------------
# src.evidence — references
# ---------------------------------------------------------------------------

class TestEvidencePackageReferences:
    def test_import_refs_heading_re(self):
        from src.evidence import REFS_HEADING_RE
        assert REFS_HEADING_RE.search("## References")

    def test_import_normalize_url(self):
        from src.evidence import normalize_url
        assert normalize_url("https://EXAMPLE.COM/") == "https://example.com"

    def test_import_dedupe_citations(self):
        from src.evidence import dedupe_citations
        assert callable(dedupe_citations)

    def test_import_build_references_section(self):
        from src.evidence import build_references_section
        assert callable(build_references_section)

    def test_import_inject_references_section(self):
        from src.evidence import inject_references_section
        assert callable(inject_references_section)

    def test_import_extract_references_section(self):
        from src.evidence import extract_references_section
        result = extract_references_section("## References\n\n1. foo\n")
        assert "References" in result

    def test_import_generate_references_for_synthesis(self):
        from src.evidence import generate_references_for_synthesis
        assert callable(generate_references_for_synthesis)


# ---------------------------------------------------------------------------
# src.evidence — provenance
# ---------------------------------------------------------------------------

class TestEvidencePackageProvenance:
    def test_import_extract_citations(self):
        from src.evidence import extract_citations
        assert callable(extract_citations)

    def test_import_extract_claims(self):
        from src.evidence import extract_claims
        assert callable(extract_claims)

    def test_import_score_evidence_quality(self):
        from src.evidence import score_evidence_quality
        assert callable(score_evidence_quality)

    def test_import_write_provenance_artifacts_bundle(self):
        from src.evidence import write_provenance_artifacts_bundle
        assert callable(write_provenance_artifacts_bundle)


# ---------------------------------------------------------------------------
# Backward compatibility — flat imports still work
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_deliverable_pipeline_still_importable(self):
        from src.deliverable_pipeline import DeliverablePipeline
        assert DeliverablePipeline

    def test_deliverable_classes_still_importable(self):
        from src.deliverable_classes import DeliverableClass, create_pipeline
        assert DeliverableClass.PAPER

    def test_citation_verification_still_importable(self):
        from src.citation_verification import VerificationViolation
        assert VerificationViolation

    def test_export_bundle_still_importable(self):
        from src.export_bundle import ExportBundle, build_export_bundle
        assert build_export_bundle

    def test_references_still_importable(self):
        from src.references import REFS_HEADING_RE, extract_references_section
        assert REFS_HEADING_RE
