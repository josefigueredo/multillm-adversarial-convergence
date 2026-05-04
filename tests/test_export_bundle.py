"""TDD tests for MM11 Step 4 — export bundles.

All tests are written before the implementation exists.
"""

import pytest

from src.deliverables.pipeline import (
    ExportArtifact,
    PackageArtifact,
    RevisionArtifact,
    SynthesisArtifact,
    DeliverablePipeline,
    PipelineStage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthesis(
    body: str = "## Abstract\nContent.\n",
    key_findings: tuple[str, ...] = ("finding A", "finding B"),
    source_count: int = 5,
) -> SynthesisArtifact:
    return SynthesisArtifact(
        title="Test Title",
        body=body,
        key_findings=key_findings,
        source_count=source_count,
    )


def _revision(
    revised_body: str = "## Abstract\nRevised content.\n",
    revision_notes: tuple[str, ...] = ("clarified intro", "tightened conclusion"),
) -> RevisionArtifact:
    return RevisionArtifact(revised_body=revised_body, revision_notes=revision_notes)


def _package(format: str = "latex", metadata: dict | None = None) -> PackageArtifact:
    return PackageArtifact(format=format, metadata=metadata or {"author": "Tester"})


def _export(
    output_paths: tuple[str, ...] = ("out/paper.pdf",),
    exported_at: str = "2024-06-01T12:00:00Z",
) -> ExportArtifact:
    return ExportArtifact(output_paths=output_paths, exported_at=exported_at)


def _full_pipeline(
    topic: str = "LLM Safety",
    deliverable_class: str | None = "paper",
    synthesis_body: str = "## Abstract\nContent.\n",
    revised_body: str = "## Abstract\nRevised content.\n",
    revision_notes: tuple[str, ...] = ("note A",),
    export_paths: tuple[str, ...] = ("out/paper.pdf",),
    exported_at: str = "2024-06-01T12:00:00Z",
) -> DeliverablePipeline:
    """Return a fully completed pipeline at EXPORT stage."""
    p = DeliverablePipeline(topic=topic, deliverable_class=deliverable_class)
    p = p.with_synthesis(_synthesis(body=synthesis_body))
    p = p.with_revision(_revision(revised_body=revised_body, revision_notes=revision_notes))
    p = p.with_package(_package())
    p = p.with_export(_export(output_paths=export_paths, exported_at=exported_at))
    return p


# ---------------------------------------------------------------------------
# build_export_bundle — entry contract
# ---------------------------------------------------------------------------

class TestBuildExportBundleEntryContract:
    def test_raises_for_pending_pipeline(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = DeliverablePipeline(topic="T")
        with pytest.raises(ValueError, match="EXPORT"):
            build_export_bundle(p)

    def test_raises_for_synthesize_stage(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = DeliverablePipeline(topic="T").with_synthesis(_synthesis())
        with pytest.raises(ValueError, match="EXPORT"):
            build_export_bundle(p)

    def test_raises_for_revise_stage(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = DeliverablePipeline(topic="T").with_synthesis(_synthesis()).with_revision(_revision())
        with pytest.raises(ValueError, match="EXPORT"):
            build_export_bundle(p)

    def test_raises_for_package_stage(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = (
            DeliverablePipeline(topic="T")
            .with_synthesis(_synthesis())
            .with_revision(_revision())
            .with_package(_package())
        )
        with pytest.raises(ValueError, match="EXPORT"):
            build_export_bundle(p)

    def test_raises_when_export_artifact_has_empty_paths(self):
        from src.deliverables.export_bundle import build_export_bundle
        bad_export = _export(output_paths=())
        p = (
            DeliverablePipeline(topic="T")
            .with_synthesis(_synthesis())
            .with_revision(_revision())
            .with_package(_package())
            .with_export(bad_export)
        )
        with pytest.raises(ValueError):
            build_export_bundle(p)

    def test_raises_when_export_artifact_has_invalid_exported_at(self):
        from src.deliverables.export_bundle import build_export_bundle
        bad_export = _export(exported_at="not-a-date")
        p = (
            DeliverablePipeline(topic="T")
            .with_synthesis(_synthesis())
            .with_revision(_revision())
            .with_package(_package())
            .with_export(bad_export)
        )
        with pytest.raises(ValueError):
            build_export_bundle(p)


# ---------------------------------------------------------------------------
# build_export_bundle — BundleManifest fields
# ---------------------------------------------------------------------------

class TestBundleManifest:
    def test_manifest_topic_matches_pipeline(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline(topic="AI Governance"))
        assert bundle.manifest.topic == "AI Governance"

    def test_manifest_format_matches_package(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline())
        assert bundle.manifest.format == "latex"

    def test_manifest_deliverable_class_matches_pipeline(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline(deliverable_class="executive_brief"))
        assert bundle.manifest.deliverable_class == "executive_brief"

    def test_manifest_deliverable_class_none_for_unclassed_pipeline(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline(deliverable_class=None))
        assert bundle.manifest.deliverable_class is None

    def test_manifest_bundle_id_is_non_empty(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline())
        assert bundle.manifest.bundle_id and isinstance(bundle.manifest.bundle_id, str)

    def test_manifest_bundle_ids_are_unique(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = _full_pipeline()
        b1 = build_export_bundle(p)
        b2 = build_export_bundle(p)
        assert b1.manifest.bundle_id != b2.manifest.bundle_id


# ---------------------------------------------------------------------------
# build_export_bundle — BundleProvenance fields
# ---------------------------------------------------------------------------

class TestBundleProvenance:
    def test_provenance_source_count_from_synthesis(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = _full_pipeline()
        # synthesis has source_count=5 (default in _synthesis helper)
        bundle = build_export_bundle(p)
        assert bundle.provenance.source_count == 5

    def test_provenance_key_findings_from_synthesis(self):
        from src.deliverables.export_bundle import build_export_bundle
        findings = ("finding X", "finding Y", "finding Z")
        p = DeliverablePipeline(topic="T").with_synthesis(
            _synthesis(key_findings=findings)
        ).with_revision(_revision()).with_package(_package()).with_export(_export())
        bundle = build_export_bundle(p)
        assert bundle.provenance.key_findings == findings


# ---------------------------------------------------------------------------
# build_export_bundle — revision_notes and references_section
# ---------------------------------------------------------------------------

class TestBundleRevisionAndReferences:
    def test_revision_notes_from_revision_artifact(self):
        from src.deliverables.export_bundle import build_export_bundle
        notes = ("restructured section 2", "added citations")
        p = _full_pipeline(revision_notes=notes)
        bundle = build_export_bundle(p)
        assert bundle.revision_notes == notes

    def test_references_section_extracted_from_revised_body(self):
        from src.deliverables.export_bundle import build_export_bundle
        revised = (
            "## Introduction\nContent.\n\n"
            "## References\n\n"
            "1. [Smith 2023](https://example.com)\n"
        )
        p = _full_pipeline(revised_body=revised)
        bundle = build_export_bundle(p)
        assert "References" in bundle.references_section
        assert "Smith 2023" in bundle.references_section

    def test_references_section_empty_when_none_in_revised_body(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = _full_pipeline(revised_body="## Introduction\nContent only.")
        bundle = build_export_bundle(p)
        assert bundle.references_section == ""

    def test_references_section_uses_revised_body_not_synthesis_body(self):
        """References should reflect what revision produced, not original synthesis."""
        from src.deliverables.export_bundle import build_export_bundle
        synthesis_body = (
            "## Abstract\nContent.\n\n"
            "## References\n\n"
            "1. [Old Ref](https://old.com)\n"
        )
        revised_body = (
            "## Abstract\nRevised content.\n\n"
            "## References\n\n"
            "1. [New Ref](https://new.com)\n"
        )
        p = DeliverablePipeline(topic="T").with_synthesis(
            _synthesis(body=synthesis_body)
        ).with_revision(
            _revision(revised_body=revised_body)
        ).with_package(_package()).with_export(_export())
        bundle = build_export_bundle(p)
        assert "New Ref" in bundle.references_section
        assert "Old Ref" not in bundle.references_section

    def test_bibliography_heading_also_extracted(self):
        from src.deliverables.export_bundle import build_export_bundle
        revised = "## Intro\nText.\n\n# Bibliography\n\n1. Some entry\n"
        p = _full_pipeline(revised_body=revised)
        bundle = build_export_bundle(p)
        assert "Bibliography" in bundle.references_section
        assert "Some entry" in bundle.references_section


# ---------------------------------------------------------------------------
# build_export_bundle — export field
# ---------------------------------------------------------------------------

class TestBundleExportField:
    def test_export_field_matches_pipeline_export(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = _full_pipeline(export_paths=("out/doc.pdf", "out/doc.tex"), exported_at="2024-09-01T10:00:00Z")
        bundle = build_export_bundle(p)
        assert bundle.export.output_paths == ("out/doc.pdf", "out/doc.tex")
        assert bundle.export.exported_at == "2024-09-01T10:00:00Z"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestExportBundleSerialization:
    def test_bundle_manifest_round_trip(self):
        from src.deliverables.export_bundle import BundleManifest
        m = BundleManifest(
            bundle_id="abc-123",
            topic="Test",
            deliverable_class="paper",
            format="latex",
        )
        assert BundleManifest.from_dict(m.to_dict()) == m

    def test_bundle_manifest_round_trip_none_class(self):
        from src.deliverables.export_bundle import BundleManifest
        m = BundleManifest(bundle_id="x", topic="T", deliverable_class=None, format="markdown")
        assert BundleManifest.from_dict(m.to_dict()) == m

    def test_bundle_provenance_round_trip(self):
        from src.deliverables.export_bundle import BundleProvenance
        prov = BundleProvenance(source_count=7, key_findings=("f1", "f2"))
        assert BundleProvenance.from_dict(prov.to_dict()) == prov

    def test_export_bundle_round_trip(self):
        from src.deliverables.export_bundle import build_export_bundle
        p = _full_pipeline()
        bundle = build_export_bundle(p)
        assert type(bundle).from_dict(bundle.to_dict()) == bundle

    def test_export_bundle_to_dict_has_expected_keys(self):
        from src.deliverables.export_bundle import build_export_bundle
        bundle = build_export_bundle(_full_pipeline())
        d = bundle.to_dict()
        assert {"manifest", "provenance", "revision_notes", "references_section", "export"} <= d.keys()
