"""MM15 Step 2 — deliverables Phase A: canonical module paths + shim backward compat."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical new-path imports
# ---------------------------------------------------------------------------

class TestDeliverablesCanonicalPaths:
    def test_pipeline_module_importable_at_canonical_path(self):
        from src.deliverables import pipeline  # noqa: F401
        assert pipeline is not None

    def test_classes_module_importable_at_canonical_path(self):
        from src.deliverables import classes  # noqa: F401
        assert classes is not None

    def test_citation_verification_module_importable_at_canonical_path(self):
        from src.deliverables import citation_verification  # noqa: F401
        assert citation_verification is not None

    def test_report_exports_module_importable_at_canonical_path(self):
        from src.deliverables import report_exports  # noqa: F401
        assert report_exports is not None

    def test_deliverable_pipeline_class_from_canonical_pipeline(self):
        from src.deliverables.pipeline import DeliverablePipeline
        assert DeliverablePipeline is not None

    def test_pipeline_stage_from_canonical_pipeline(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage is not None

    def test_create_pipeline_from_canonical_classes(self):
        from src.deliverables.classes import create_pipeline
        assert callable(create_pipeline)

    def test_deliverable_class_from_canonical_classes(self):
        from src.deliverables.classes import DeliverableClass
        assert DeliverableClass is not None

    def test_verify_synthesis_citations_from_canonical_citation_verification(self):
        from src.deliverables.citation_verification import verify_synthesis_citations
        assert callable(verify_synthesis_citations)

    def test_verification_violation_from_canonical_citation_verification(self):
        from src.deliverables.citation_verification import VerificationViolation
        assert VerificationViolation is not None

    def test_write_reporting_artifacts_from_canonical_report_exports(self):
        from src.deliverables.report_exports import write_reporting_artifacts
        assert callable(write_reporting_artifacts)


# ---------------------------------------------------------------------------
# Old flat-path imports must still work via compatibility shims
# ---------------------------------------------------------------------------

class TestDeliverablesShimBackwardCompat:
    def test_deliverable_pipeline_importable_from_src_deliverable_pipeline(self):
        from src.deliverable_pipeline import DeliverablePipeline
        assert DeliverablePipeline is not None

    def test_pipeline_stage_importable_from_src_deliverable_pipeline(self):
        from src.deliverable_pipeline import PipelineStage
        assert PipelineStage is not None

    def test_create_pipeline_importable_from_src_deliverable_classes(self):
        from src.deliverable_classes import create_pipeline
        assert callable(create_pipeline)

    def test_verify_synthesis_citations_from_src_citation_verification(self):
        from src.citation_verification import verify_synthesis_citations
        assert callable(verify_synthesis_citations)

    def test_write_reporting_artifacts_from_src_report_exports(self):
        from src.report_exports import write_reporting_artifacts
        assert callable(write_reporting_artifacts)


# ---------------------------------------------------------------------------
# Regression: existing deliverables package __init__ API still intact
# ---------------------------------------------------------------------------

class TestDeliverablesPackageApiUnchanged:
    def test_deliverable_pipeline_via_deliverables_init(self):
        from src.deliverables import DeliverablePipeline
        assert DeliverablePipeline is not None

    def test_create_pipeline_via_deliverables_init(self):
        from src.deliverables import create_pipeline
        assert callable(create_pipeline)

    def test_verify_synthesis_citations_via_deliverables_init(self):
        from src.deliverables import verify_synthesis_citations
        assert callable(verify_synthesis_citations)
