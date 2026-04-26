"""Export bundles — MM11 Step 4.

Formalizes the export bundle as a first-class artifact that combines:

- **Manifest** — pipeline identity (topic, class, format, bundle ID)
- **Provenance** — research origin (source count, key findings)
- **Revision notes** — changes applied during the revise stage
- **References section** — deterministic reference block extracted from
  the final revised body (not the original synthesis)
- **Export artifact** — the underlying :class:`~src.deliverable_pipeline.ExportArtifact`
  (output paths, timestamp)

Use :func:`build_export_bundle` to create a bundle from a fully completed
:class:`~src.deliverable_pipeline.DeliverablePipeline`.  The factory validates
both pipeline stage and export artifact integrity before constructing the bundle.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .citation_verification import verify_export_artifact
from .deliverable_pipeline import DeliverablePipeline, ExportArtifact, PipelineStage
from .references import extract_references_section


# ---------------------------------------------------------------------------
# BundleManifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleManifest:
    """Identity metadata for an export bundle.

    Attributes
    ----------
    bundle_id:
        Unique identifier generated at bundle creation time.
    topic:
        Topic of the deliverable, mirroring
        :attr:`~src.deliverable_pipeline.DeliverablePipeline.topic`.
    deliverable_class:
        The :class:`~src.deliverable_classes.DeliverableClass` value (as a
        string) governing this pipeline, or ``None`` for unclassed pipelines.
    format:
        Target output format from the package stage (e.g. ``"latex"``).
    """

    bundle_id: str
    topic: str
    deliverable_class: str | None
    format: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "topic": self.topic,
            "deliverable_class": self.deliverable_class,
            "format": self.format,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BundleManifest":
        return cls(
            bundle_id=d["bundle_id"],
            topic=d["topic"],
            deliverable_class=d.get("deliverable_class"),
            format=d["format"],
        )


# ---------------------------------------------------------------------------
# BundleProvenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleProvenance:
    """Research-origin metadata for an export bundle.

    Attributes
    ----------
    source_count:
        Number of research sources consumed during synthesis, mirroring
        :attr:`~src.deliverable_pipeline.SynthesisArtifact.source_count`.
    key_findings:
        Top-level findings from the synthesis stage.
    """

    source_count: int
    key_findings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "key_findings": list(self.key_findings),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BundleProvenance":
        return cls(
            source_count=int(d["source_count"]),
            key_findings=tuple(d.get("key_findings", [])),
        )


# ---------------------------------------------------------------------------
# ExportBundle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportBundle:
    """Immutable snapshot of a completed, export-ready deliverable.

    Combines pipeline-stage artifacts into a single inspectable object.
    The :attr:`export` field is the canonical source for output paths and
    timestamps; other fields are derived summaries that must not contradict it.

    Attributes
    ----------
    manifest:
        Pipeline identity (topic, class, format, bundle ID).
    provenance:
        Research origin (source count, key findings).
    revision_notes:
        Ordered notes describing what changed during the revise stage.
    references_section:
        Full ``## References`` / ``## Bibliography`` section extracted from
        the *revised* body, or an empty string if none was present.
    export:
        The underlying :class:`~src.deliverable_pipeline.ExportArtifact`
        (output paths, exported-at timestamp).
    """

    manifest: BundleManifest
    provenance: BundleProvenance
    revision_notes: tuple[str, ...]
    references_section: str
    export: ExportArtifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "provenance": self.provenance.to_dict(),
            "revision_notes": list(self.revision_notes),
            "references_section": self.references_section,
            "export": self.export.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExportBundle":
        return cls(
            manifest=BundleManifest.from_dict(d["manifest"]),
            provenance=BundleProvenance.from_dict(d["provenance"]),
            revision_notes=tuple(d.get("revision_notes", [])),
            references_section=d.get("references_section", ""),
            export=ExportArtifact.from_dict(d["export"]),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_export_bundle(pipeline: DeliverablePipeline) -> ExportBundle:
    """Build an :class:`ExportBundle` from a completed *pipeline*.

    Parameters
    ----------
    pipeline:
        Must be at :attr:`~src.deliverable_pipeline.PipelineStage.EXPORT` stage.

    Raises
    ------
    ValueError
        If the pipeline has not reached the EXPORT stage, or if the pipeline's
        :class:`~src.deliverable_pipeline.ExportArtifact` fails
        :func:`~src.citation_verification.verify_export_artifact` checks.
    """
    if pipeline.completed_stage != PipelineStage.EXPORT:
        raise ValueError(
            f"pipeline must be at EXPORT stage to build a bundle "
            f"(current: {pipeline.completed_stage.value!r})"
        )

    violations = verify_export_artifact(pipeline.export)  # type: ignore[arg-type]
    if violations:
        raise ValueError(
            f"export artifact is not publication-ready: {violations[0].message}"
        )

    assert pipeline.synthesis is not None  # guaranteed by stage check
    assert pipeline.revision is not None
    assert pipeline.package is not None
    assert pipeline.export is not None

    refs = extract_references_section(pipeline.revision.revised_body)

    return ExportBundle(
        manifest=BundleManifest(
            bundle_id=str(uuid.uuid4()),
            topic=pipeline.topic,
            deliverable_class=pipeline.deliverable_class,
            format=pipeline.package.format,
        ),
        provenance=BundleProvenance(
            source_count=pipeline.synthesis.source_count,
            key_findings=pipeline.synthesis.key_findings,
        ),
        revision_notes=pipeline.revision.revision_notes,
        references_section=refs,
        export=pipeline.export,
    )
