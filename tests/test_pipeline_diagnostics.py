"""TDD tests for MM11 Step 5 — doctor/explain for publication pipeline states.

All tests are written before the implementation exists.
"""

import pytest

from src.deliverable_pipeline import (
    DeliverablePipeline,
    ExportArtifact,
    PackageArtifact,
    PipelineStage,
    RevisionArtifact,
    SynthesisArtifact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthesis(
    body: str = "## Abstract\nContent.\n",
    key_findings: tuple[str, ...] = ("finding A",),
    source_count: int = 3,
) -> SynthesisArtifact:
    return SynthesisArtifact(title="Test", body=body, key_findings=key_findings, source_count=source_count)


def _revision(notes: tuple[str, ...] = ("note A",)) -> RevisionArtifact:
    return RevisionArtifact(revised_body="## Abstract\nRevised.\n", revision_notes=notes)


def _package(fmt: str = "latex") -> PackageArtifact:
    return PackageArtifact(format=fmt)


def _export(paths: tuple[str, ...] = ("out/paper.pdf",), at: str = "2024-06-01T12:00:00Z") -> ExportArtifact:
    return ExportArtifact(output_paths=paths, exported_at=at)


def _pipeline_at(stage: str, topic: str = "AI Safety", deliverable_class: str | None = None) -> DeliverablePipeline:
    """Return a pipeline advanced to *stage*."""
    p = DeliverablePipeline(topic=topic, deliverable_class=deliverable_class)
    if stage == "pending":
        return p
    p = p.with_synthesis(_synthesis())
    if stage == "synthesize":
        return p
    p = p.with_revision(_revision())
    if stage == "revise":
        return p
    p = p.with_package(_package())
    if stage == "package":
        return p
    p = p.with_export(_export())
    return p  # export


# ---------------------------------------------------------------------------
# explain_pipeline_text — basic structure
# ---------------------------------------------------------------------------

class TestExplainPipelineText:
    def test_output_includes_topic(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("pending", topic="Quantum Computing")
        assert "Quantum Computing" in explain_pipeline_text(p)

    def test_output_includes_deliverable_class_when_set(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("pending", deliverable_class="paper")
        assert "paper" in explain_pipeline_text(p)

    def test_output_notes_unclassed_when_no_class(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("pending")
        text = explain_pipeline_text(p)
        # should indicate unclassed, not silently omit
        assert "unclassed" in text.lower() or "none" in text.lower()

    def test_pending_stage_shows_pending(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("pending")
        assert "pending" in explain_pipeline_text(p).lower()

    def test_synthesize_stage_shows_completed(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("synthesize")
        text = explain_pipeline_text(p)
        assert "synthesize" in text.lower() or "synthesis" in text.lower()

    def test_revise_stage_shows_revision_notes_count(self):
        from src.explain import explain_pipeline_text
        p = DeliverablePipeline(topic="T").with_synthesis(
            _synthesis()
        ).with_revision(_revision(notes=("note 1", "note 2", "note 3")))
        text = explain_pipeline_text(p)
        assert "3" in text  # 3 revision notes

    def test_package_stage_shows_format(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("package")
        assert "latex" in explain_pipeline_text(p).lower()

    def test_export_stage_shows_all_stages_complete(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("export")
        text = explain_pipeline_text(p)
        # all four stage words should appear
        for word in ("synthesize", "revise", "package", "export"):
            assert word in text.lower()

    def test_export_stage_shows_output_paths(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("export")
        assert "out/paper.pdf" in explain_pipeline_text(p)

    def test_export_stage_shows_timestamp(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("export")
        assert "2024-06-01" in explain_pipeline_text(p)

    def test_completed_stage_shown_in_output(self):
        from src.explain import explain_pipeline_text
        p = _pipeline_at("package")
        text = explain_pipeline_text(p)
        assert "package" in text.lower()

    def test_source_count_shown_after_synthesis(self):
        from src.explain import explain_pipeline_text
        p = DeliverablePipeline(topic="T").with_synthesis(_synthesis(source_count=7))
        text = explain_pipeline_text(p)
        assert "7" in text  # 7 sources


# ---------------------------------------------------------------------------
# doctor_pipeline — entry contract and healthy states
# ---------------------------------------------------------------------------

class TestDoctorPipelineHealthy:
    def test_pending_pipeline_returns_report(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("pending")
        report = doctor_pipeline(p)
        assert report is not None

    def test_pending_pipeline_is_healthy(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("pending")
        assert doctor_pipeline(p).exit_code == 0

    def test_full_valid_export_pipeline_is_healthy(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("export")
        assert doctor_pipeline(p).exit_code == 0

    def test_report_text_includes_topic(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("pending", topic="Biosecurity")
        assert "Biosecurity" in doctor_pipeline(p).text

    def test_report_text_includes_stage(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("synthesize")
        text = doctor_pipeline(p).text
        assert "synthesize" in text.lower() or "synthesis" in text.lower()

    def test_report_text_includes_health_label(self):
        from src.doctor import doctor_pipeline
        p = _pipeline_at("pending")
        assert "HEALTH" in doctor_pipeline(p).text

    def test_paper_with_citations_is_healthy(self):
        """PAPER class with proper references section should be healthy."""
        from src.doctor import doctor_pipeline
        body = (
            "## Abstract\nContent.\n\n"
            "## References\n\n"
            "1. [Smith 2023](https://example.com)\n"
        )
        p = DeliverablePipeline(topic="T", deliverable_class="paper").with_synthesis(
            _synthesis(body=body)
        )
        assert doctor_pipeline(p).exit_code == 0


# ---------------------------------------------------------------------------
# doctor_pipeline — warning states
# ---------------------------------------------------------------------------

class TestDoctorPipelineWarnings:
    def test_paper_without_citations_produces_warning(self):
        """Synthesis for PAPER class with no references section triggers a warning."""
        from src.doctor import doctor_pipeline
        body = "## Abstract\nContent with no citations at all."
        p = DeliverablePipeline(topic="T", deliverable_class="paper").with_synthesis(
            _synthesis(body=body)
        )
        report = doctor_pipeline(p)
        assert report.exit_code == 1

    def test_paper_without_citations_warning_message_is_informative(self):
        from src.doctor import doctor_pipeline
        body = "## Abstract\nNo references here."
        p = DeliverablePipeline(topic="T", deliverable_class="paper").with_synthesis(
            _synthesis(body=body)
        )
        text = doctor_pipeline(p).text
        # should mention citations/references somewhere
        assert "citation" in text.lower() or "reference" in text.lower()

    def test_export_with_empty_paths_produces_warning(self):
        from src.doctor import doctor_pipeline
        bad_export = ExportArtifact(output_paths=(), exported_at="2024-06-01T00:00:00Z")
        p = (
            DeliverablePipeline(topic="T")
            .with_synthesis(_synthesis())
            .with_revision(_revision())
            .with_package(_package())
            .with_export(bad_export)
        )
        assert doctor_pipeline(p).exit_code == 1

    def test_export_with_invalid_timestamp_produces_warning(self):
        from src.doctor import doctor_pipeline
        bad_export = ExportArtifact(output_paths=("out/paper.pdf",), exported_at="bad-date")
        p = (
            DeliverablePipeline(topic="T")
            .with_synthesis(_synthesis())
            .with_revision(_revision())
            .with_package(_package())
            .with_export(bad_export)
        )
        assert doctor_pipeline(p).exit_code == 1

    def test_non_paper_class_without_citations_is_healthy(self):
        """Classes with requires_citations=False should not warn about missing refs."""
        from src.doctor import doctor_pipeline
        body = "## Key Takeaways\nNo references needed."
        p = DeliverablePipeline(topic="T", deliverable_class="executive_brief").with_synthesis(
            _synthesis(body=body)
        )
        assert doctor_pipeline(p).exit_code == 0

    def test_unclassed_pipeline_without_citations_is_healthy(self):
        """An unclassed pipeline has no citation requirement."""
        from src.doctor import doctor_pipeline
        p = DeliverablePipeline(topic="T").with_synthesis(_synthesis())
        assert doctor_pipeline(p).exit_code == 0

    def test_warning_section_present_when_issues_found(self):
        from src.doctor import doctor_pipeline
        body = "## Abstract\nNo citations."
        p = DeliverablePipeline(topic="T", deliverable_class="paper").with_synthesis(
            _synthesis(body=body)
        )
        assert "WARN" in doctor_pipeline(p).text or "[!]" in doctor_pipeline(p).text
