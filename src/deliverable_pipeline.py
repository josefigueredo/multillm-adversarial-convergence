"""Deliverable pipeline model — MM11 Step 1.

Defines the staged publication pipeline:

    synthesize → revise → package → export

Each stage produces an immutable artifact.  :class:`DeliverablePipeline`
holds the accumulated artifacts and enforces stage ordering.

Key design decisions
--------------------
- Artifacts do **not** nest — the pipeline is the single source of truth
  for what has been completed at each stage.  Nesting would create multiple
  inconsistent sources of truth.
- ``with_X()`` methods clear all downstream artifacts so the pipeline is
  never in a stale state after an upstream replacement.
- ``completed_stage`` reports the highest stage that has been completed,
  not the next required one — naming is explicit to avoid ambiguity.
- ``PackageArtifact.metadata`` uses ``types.MappingProxyType`` (same
  pattern as ``TargetContext.env_vars`` in MM10) for deep immutability.
"""

from __future__ import annotations

import dataclasses
import types
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# PipelineStage
# ---------------------------------------------------------------------------

class PipelineStage(str, Enum):
    """Ordered stages of the publication pipeline."""

    PENDING = "pending"
    SYNTHESIZE = "synthesize"
    REVISE = "revise"
    PACKAGE = "package"
    EXPORT = "export"


# ---------------------------------------------------------------------------
# SynthesisArtifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SynthesisArtifact:
    """Output of the *synthesize* stage.

    Attributes
    ----------
    title:
        Title of the synthesized deliverable.
    body:
        Full synthesized content.
    key_findings:
        Ordered top-level findings extracted from the knowledge base.
    source_count:
        Number of research sources consumed during synthesis.
    """

    title: str
    body: str
    key_findings: tuple[str, ...] = ()
    source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "body": self.body,
            "key_findings": list(self.key_findings),
            "source_count": self.source_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SynthesisArtifact":
        return cls(
            title=d["title"],
            body=d["body"],
            key_findings=tuple(d.get("key_findings", [])),
            source_count=int(d.get("source_count", 0)),
        )


# ---------------------------------------------------------------------------
# RevisionArtifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RevisionArtifact:
    """Output of the *revise* stage.

    Attributes
    ----------
    revised_body:
        Content after applying critique-driven revisions.
    revision_notes:
        Ordered notes describing what was changed and why.
    """

    revised_body: str
    revision_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "revised_body": self.revised_body,
            "revision_notes": list(self.revision_notes),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RevisionArtifact":
        return cls(
            revised_body=d["revised_body"],
            revision_notes=tuple(d.get("revision_notes", [])),
        )


# ---------------------------------------------------------------------------
# PackageArtifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PackageArtifact:
    """Output of the *package* stage.

    Attributes
    ----------
    format:
        Target output format, e.g. ``"markdown"``, ``"latex"``, ``"docx"``.
    metadata:
        Immutable key/value metadata (author, year, venue, …).
        Exposed as :class:`types.MappingProxyType` so callers cannot widen
        the package contract after construction.
    """

    format: str
    metadata: types.MappingProxyType  # type: ignore[type-arg]

    def __init__(
        self,
        format: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        object.__setattr__(self, "format", format)
        object.__setattr__(
            self,
            "metadata",
            types.MappingProxyType(dict(metadata or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PackageArtifact":
        return cls(
            format=d["format"],
            metadata=dict(d.get("metadata", {})),
        )


# ---------------------------------------------------------------------------
# ExportArtifact
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExportArtifact:
    """Output of the *export* stage.

    Attributes
    ----------
    output_paths:
        Paths (as strings) to the exported files.
    exported_at:
        ISO 8601 timestamp of when the export completed.
    """

    output_paths: tuple[str, ...] = ()
    exported_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_paths": list(self.output_paths),
            "exported_at": self.exported_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ExportArtifact":
        return cls(
            output_paths=tuple(d.get("output_paths", [])),
            exported_at=d.get("exported_at", ""),
        )


# ---------------------------------------------------------------------------
# DeliverablePipeline
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeliverablePipeline:
    """Immutable snapshot of a deliverable's publication pipeline state.

    The pipeline holds one artifact per stage.  Artifacts do **not** nest —
    this is the sole source of truth for what has been completed.

    Stage ordering is enforced in ``__post_init__``: later stages cannot be
    present without all earlier stages having been completed.

    Use ``with_synthesis()``, ``with_revision()``, ``with_package()``, and
    ``with_export()`` to advance stages.  Each method returns a **new**
    :class:`DeliverablePipeline` instance with downstream stages cleared.
    """

    topic: str
    synthesis: SynthesisArtifact | None = None
    revision: RevisionArtifact | None = None
    package: PackageArtifact | None = None
    export: ExportArtifact | None = None
    deliverable_class: str | None = None  # DeliverableClass.value when set via create_pipeline()

    def __post_init__(self) -> None:
        if not self.topic:
            raise ValueError("DeliverablePipeline.topic must not be empty")
        if self.revision is not None and self.synthesis is None:
            raise ValueError("revision requires synthesis")
        if self.package is not None and self.revision is None:
            raise ValueError("package requires revision")
        if self.export is not None and self.package is None:
            raise ValueError("export requires package")

    @property
    def completed_stage(self) -> PipelineStage:
        """Return the highest pipeline stage that has been completed."""
        if self.export is not None:
            return PipelineStage.EXPORT
        if self.package is not None:
            return PipelineStage.PACKAGE
        if self.revision is not None:
            return PipelineStage.REVISE
        if self.synthesis is not None:
            return PipelineStage.SYNTHESIZE
        return PipelineStage.PENDING

    # ── Stage-transition helpers ──────────────────────────────────────────────

    def with_synthesis(self, artifact: SynthesisArtifact) -> "DeliverablePipeline":
        """Return a new pipeline with synthesis applied and downstream cleared."""
        return dataclasses.replace(
            self,
            synthesis=artifact,
            revision=None,
            package=None,
            export=None,
        )

    def with_revision(self, artifact: RevisionArtifact) -> "DeliverablePipeline":
        """Return a new pipeline with revision applied and downstream cleared.

        Raises
        ------
        ValueError
            If synthesis has not been completed yet.
        """
        return dataclasses.replace(
            self,
            revision=artifact,
            package=None,
            export=None,
        )

    def with_package(self, artifact: PackageArtifact) -> "DeliverablePipeline":
        """Return a new pipeline with package applied and export cleared.

        Raises
        ------
        ValueError
            If revision has not been completed yet.
        """
        return dataclasses.replace(
            self,
            package=artifact,
            export=None,
        )

    def with_export(self, artifact: ExportArtifact) -> "DeliverablePipeline":
        """Return a new pipeline with export applied.

        Raises
        ------
        ValueError
            If package has not been completed yet.
        """
        return dataclasses.replace(self, export=artifact)

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "deliverable_class": self.deliverable_class,
            "synthesis": self.synthesis.to_dict() if self.synthesis else None,
            "revision": self.revision.to_dict() if self.revision else None,
            "package": self.package.to_dict() if self.package else None,
            "export": self.export.to_dict() if self.export else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DeliverablePipeline":
        return cls(
            topic=d["topic"],
            deliverable_class=d.get("deliverable_class"),
            synthesis=SynthesisArtifact.from_dict(d["synthesis"]) if d.get("synthesis") else None,
            revision=RevisionArtifact.from_dict(d["revision"]) if d.get("revision") else None,
            package=PackageArtifact.from_dict(d["package"]) if d.get("package") else None,
            export=ExportArtifact.from_dict(d["export"]) if d.get("export") else None,
        )
