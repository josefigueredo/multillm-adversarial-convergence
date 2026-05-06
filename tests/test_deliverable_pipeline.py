"""Tests for Deliverable pipeline model.

Covers:
- PipelineStage: enum values (pending, synthesize, revise, package, export)
- SynthesisArtifact: fields, frozen, defaults, to_dict/from_dict
- RevisionArtifact: fields, frozen, defaults, to_dict/from_dict
- PackageArtifact: fields, frozen, immutable metadata, to_dict/from_dict
- ExportArtifact: fields, frozen, defaults, to_dict/from_dict
- DeliverablePipeline: topic required, completed_stage property,
  stage-ordering enforcement, with_X clears downstream, frozen, to_dict/from_dict
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# PipelineStage
# ---------------------------------------------------------------------------

class TestPipelineStage:
    def test_pending_value(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage.PENDING.value == "pending"

    def test_synthesize_value(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage.SYNTHESIZE.value == "synthesize"

    def test_revise_value(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage.REVISE.value == "revise"

    def test_package_value(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage.PACKAGE.value == "package"

    def test_export_value(self):
        from src.deliverables.pipeline import PipelineStage
        assert PipelineStage.EXPORT.value == "export"


# ---------------------------------------------------------------------------
# SynthesisArtifact
# ---------------------------------------------------------------------------

class TestSynthesisArtifact:
    def _make(self, **kw):
        from src.deliverables.pipeline import SynthesisArtifact
        defaults = dict(title="LLM Safety", body="Body text")
        return SynthesisArtifact(**{**defaults, **kw})

    def test_title_and_body_required(self):
        from src.deliverables.pipeline import SynthesisArtifact
        a = SynthesisArtifact(title="T", body="B")
        assert a.title == "T"
        assert a.body == "B"

    def test_key_findings_defaults_to_empty_tuple(self):
        a = self._make()
        assert a.key_findings == ()

    def test_source_count_defaults_to_zero(self):
        a = self._make()
        assert a.source_count == 0

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        a = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.title = "new"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        a = self._make()
        d = a.to_dict()
        assert {"title", "body", "key_findings", "source_count"} <= d.keys()

    def test_to_dict_from_dict_round_trip(self):
        from src.deliverables.pipeline import SynthesisArtifact
        a = SynthesisArtifact(title="T", body="B", key_findings=("f1", "f2"), source_count=3)
        a2 = SynthesisArtifact.from_dict(a.to_dict())
        assert a2 == a


# ---------------------------------------------------------------------------
# RevisionArtifact
# ---------------------------------------------------------------------------

class TestRevisionArtifact:
    def _make(self, **kw):
        from src.deliverables.pipeline import RevisionArtifact
        defaults = dict(revised_body="Revised body text")
        return RevisionArtifact(**{**defaults, **kw})

    def test_revised_body_required(self):
        from src.deliverables.pipeline import RevisionArtifact
        a = RevisionArtifact(revised_body="Revised")
        assert a.revised_body == "Revised"

    def test_revision_notes_defaults_to_empty_tuple(self):
        a = self._make()
        assert a.revision_notes == ()

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        a = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.revised_body = "x"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        a = self._make()
        d = a.to_dict()
        assert {"revised_body", "revision_notes"} <= d.keys()

    def test_to_dict_from_dict_round_trip(self):
        from src.deliverables.pipeline import RevisionArtifact
        a = RevisionArtifact(revised_body="R", revision_notes=("note1",))
        a2 = RevisionArtifact.from_dict(a.to_dict())
        assert a2 == a


# ---------------------------------------------------------------------------
# PackageArtifact
# ---------------------------------------------------------------------------

class TestPackageArtifact:
    def _make(self, **kw):
        from src.deliverables.pipeline import PackageArtifact
        defaults = dict(format="markdown")
        return PackageArtifact(**{**defaults, **kw})

    def test_format_required(self):
        from src.deliverables.pipeline import PackageArtifact
        a = PackageArtifact(format="markdown")
        assert a.format == "markdown"

    def test_metadata_defaults_to_empty(self):
        a = self._make()
        assert len(a.metadata) == 0

    def test_metadata_is_immutable(self):
        from src.deliverables.pipeline import PackageArtifact
        a = PackageArtifact(format="markdown", metadata={"author": "Alice"})
        with pytest.raises((TypeError, AttributeError)):
            a.metadata["author"] = "Bob"  # type: ignore[index]

    def test_metadata_source_dict_isolation(self):
        from src.deliverables.pipeline import PackageArtifact
        d = {"author": "Alice"}
        a = PackageArtifact(format="pdf", metadata=d)
        d["author"] = "Bob"
        assert a.metadata["author"] == "Alice"

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        a = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.format = "pdf"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        a = self._make()
        d = a.to_dict()
        assert {"format", "metadata"} <= d.keys()

    def test_to_dict_metadata_is_plain_dict(self):
        from src.deliverables.pipeline import PackageArtifact
        a = PackageArtifact(format="pdf", metadata={"k": "v"})
        assert isinstance(a.to_dict()["metadata"], dict)

    def test_to_dict_from_dict_round_trip(self):
        from src.deliverables.pipeline import PackageArtifact
        a = PackageArtifact(format="latex", metadata={"author": "Alice", "year": "2025"})
        a2 = PackageArtifact.from_dict(a.to_dict())
        assert a2.format == a.format
        assert dict(a2.metadata) == dict(a.metadata)


# ---------------------------------------------------------------------------
# ExportArtifact
# ---------------------------------------------------------------------------

class TestExportArtifact:
    def _make(self, **kw):
        from src.deliverables.pipeline import ExportArtifact
        return ExportArtifact(**kw)

    def test_output_paths_defaults_to_empty_tuple(self):
        a = self._make()
        assert a.output_paths == ()

    def test_exported_at_defaults_to_empty_string(self):
        a = self._make()
        assert a.exported_at == ""

    def test_output_paths_stored_as_strings(self):
        a = self._make(output_paths=("/out/report.pdf",))
        assert isinstance(a.output_paths[0], str)

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        a = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.exported_at = "2025-01-01"  # type: ignore[misc]

    def test_to_dict_has_expected_keys(self):
        a = self._make()
        d = a.to_dict()
        assert {"output_paths", "exported_at"} <= d.keys()

    def test_to_dict_from_dict_round_trip(self):
        from src.deliverables.pipeline import ExportArtifact
        a = ExportArtifact(output_paths=("/out/a.pdf", "/out/b.pdf"), exported_at="2025-01-01T00:00:00Z")
        a2 = ExportArtifact.from_dict(a.to_dict())
        assert a2 == a


# ---------------------------------------------------------------------------
# DeliverablePipeline
# ---------------------------------------------------------------------------

def _synthesis():
    from src.deliverables.pipeline import SynthesisArtifact
    return SynthesisArtifact(title="T", body="B")


def _revision():
    from src.deliverables.pipeline import RevisionArtifact
    return RevisionArtifact(revised_body="R")


def _package():
    from src.deliverables.pipeline import PackageArtifact
    return PackageArtifact(format="markdown")


def _export():
    from src.deliverables.pipeline import ExportArtifact
    return ExportArtifact(output_paths=("/out/r.md",))


class TestDeliverablePipeline:
    def _pipeline(self, **kw):
        from src.deliverables.pipeline import DeliverablePipeline
        defaults = dict(topic="LLM safety")
        return DeliverablePipeline(**{**defaults, **kw})

    # ── topic validation ─────────────────────────────────────────────────────

    def test_empty_topic_raises(self):
        from src.deliverables.pipeline import DeliverablePipeline
        with pytest.raises(ValueError, match="topic"):
            DeliverablePipeline(topic="")

    # ── completed_stage ───────────────────────────────────────────────────────

    def test_initial_completed_stage_is_pending(self):
        from src.deliverables.pipeline import PipelineStage
        p = self._pipeline()
        assert p.completed_stage == PipelineStage.PENDING

    def test_after_synthesis_completed_stage_is_synthesize(self):
        from src.deliverables.pipeline import PipelineStage
        p = self._pipeline(synthesis=_synthesis())
        assert p.completed_stage == PipelineStage.SYNTHESIZE

    def test_after_revision_completed_stage_is_revise(self):
        from src.deliverables.pipeline import PipelineStage
        p = self._pipeline(synthesis=_synthesis(), revision=_revision())
        assert p.completed_stage == PipelineStage.REVISE

    def test_after_package_completed_stage_is_package(self):
        from src.deliverables.pipeline import PipelineStage
        p = self._pipeline(synthesis=_synthesis(), revision=_revision(), package=_package())
        assert p.completed_stage == PipelineStage.PACKAGE

    def test_after_export_completed_stage_is_export(self):
        from src.deliverables.pipeline import PipelineStage
        p = self._pipeline(
            synthesis=_synthesis(), revision=_revision(),
            package=_package(), export=_export(),
        )
        assert p.completed_stage == PipelineStage.EXPORT

    # ── stage-ordering enforcement ───────────────────────────────────────────

    def test_revision_without_synthesis_raises(self):
        from src.deliverables.pipeline import DeliverablePipeline
        with pytest.raises(ValueError, match="revision requires synthesis"):
            DeliverablePipeline(topic="T", revision=_revision())

    def test_package_without_revision_raises(self):
        from src.deliverables.pipeline import DeliverablePipeline
        with pytest.raises(ValueError, match="package requires revision"):
            DeliverablePipeline(topic="T", synthesis=_synthesis(), package=_package())

    def test_export_without_package_raises(self):
        from src.deliverables.pipeline import DeliverablePipeline
        with pytest.raises(ValueError, match="export requires package"):
            DeliverablePipeline(
                topic="T", synthesis=_synthesis(),
                revision=_revision(), export=_export(),
            )

    # ── with_X advances stage and clears downstream ──────────────────────────

    def test_with_synthesis_returns_new_pipeline(self):
        p = self._pipeline()
        p2 = p.with_synthesis(_synthesis())
        assert p2 is not p
        assert p2.synthesis is not None

    def test_with_synthesis_clears_downstream_stages(self):
        p = self._pipeline(
            synthesis=_synthesis(), revision=_revision(),
            package=_package(), export=_export(),
        )
        p2 = p.with_synthesis(_synthesis())
        assert p2.revision is None
        assert p2.package is None
        assert p2.export is None

    def test_with_revision_returns_new_pipeline(self):
        p = self._pipeline(synthesis=_synthesis())
        p2 = p.with_revision(_revision())
        assert p2 is not p
        assert p2.revision is not None

    def test_with_revision_clears_package_and_export(self):
        p = self._pipeline(
            synthesis=_synthesis(), revision=_revision(),
            package=_package(), export=_export(),
        )
        p2 = p.with_revision(_revision())
        assert p2.package is None
        assert p2.export is None

    def test_with_revision_without_synthesis_raises(self):
        p = self._pipeline()
        with pytest.raises(ValueError, match="revision requires synthesis"):
            p.with_revision(_revision())

    def test_with_package_clears_export(self):
        p = self._pipeline(
            synthesis=_synthesis(), revision=_revision(),
            package=_package(), export=_export(),
        )
        p2 = p.with_package(_package())
        assert p2.export is None
        assert p2.package is not None

    def test_with_package_without_revision_raises(self):
        p = self._pipeline(synthesis=_synthesis())
        with pytest.raises(ValueError, match="package requires revision"):
            p.with_package(_package())

    def test_with_export_requires_package(self):
        p = self._pipeline(synthesis=_synthesis(), revision=_revision())
        with pytest.raises(ValueError, match="export requires package"):
            p.with_export(_export())

    # ── frozen ───────────────────────────────────────────────────────────────

    def test_is_frozen(self):
        from dataclasses import FrozenInstanceError
        p = self._pipeline()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.topic = "other"  # type: ignore[misc]

    # ── to_dict / from_dict ───────────────────────────────────────────────────

    def test_to_dict_has_expected_keys(self):
        p = self._pipeline()
        d = p.to_dict()
        assert {"topic", "synthesis", "revision", "package", "export", "deliverable_class"} <= d.keys()

    def test_to_dict_from_dict_round_trip_empty(self):
        from src.deliverables.pipeline import DeliverablePipeline
        p = self._pipeline()
        p2 = DeliverablePipeline.from_dict(p.to_dict())
        assert p2.topic == p.topic
        assert p2.synthesis is None

    def test_to_dict_from_dict_round_trip_full(self):
        from src.deliverables.pipeline import DeliverablePipeline
        p = self._pipeline(
            synthesis=_synthesis(), revision=_revision(),
            package=_package(), export=_export(),
        )
        p2 = DeliverablePipeline.from_dict(p.to_dict())
        assert p2.completed_stage == p.completed_stage
        assert p2.synthesis.title == p.synthesis.title
        assert p2.revision.revised_body == p.revision.revised_body
