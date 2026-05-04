"""Deliverables domain package.

Re-exports the full public API of the publication pipeline so callers can
import from this single package boundary instead of reaching into individual
modules.  Canonical paths are ``src.deliverables.<module>``; flat-module
imports were removed in MM15 Step 7.

Contexts exposed:
- Pipeline model (stages, artifacts, :class:`DeliverablePipeline`)
- Deliverable class configs and factory
- Citation/export verification
- Export bundle assembly
"""

from __future__ import annotations

# ── Pipeline model ────────────────────────────────────────────────────────────
from .pipeline import (
    DeliverablePipeline,
    ExportArtifact,
    PackageArtifact,
    PipelineStage,
    RevisionArtifact,
    SynthesisArtifact,
)

# ── Deliverable class configs and factory ─────────────────────────────────────
from .classes import (
    CLASS_CONFIGS,
    DECISION_MEMO_CONFIG,
    EXECUTIVE_BRIEF_CONFIG,
    PAPER_CONFIG,
    TECHNICAL_DOC_CONFIG,
    DeliverableClass,
    DeliverableClassConfig,
    create_pipeline,
    get_config_for_pipeline,
    validate_synthesis_for_class,
)

# ── Citation/export verification ──────────────────────────────────────────────
from .citation_verification import (
    VerificationViolation,
    verify_body_citations,
    verify_export_artifact,
    verify_synthesis_citations,
)

# ── Export bundle assembly ────────────────────────────────────────────────────
from .export_bundle import (
    BundleManifest,
    BundleProvenance,
    ExportBundle,
    build_export_bundle,
)

__all__ = [
    # pipeline model
    "PipelineStage",
    "SynthesisArtifact",
    "RevisionArtifact",
    "PackageArtifact",
    "ExportArtifact",
    "DeliverablePipeline",
    # class configs
    "DeliverableClass",
    "DeliverableClassConfig",
    "CLASS_CONFIGS",
    "PAPER_CONFIG",
    "TECHNICAL_DOC_CONFIG",
    "EXECUTIVE_BRIEF_CONFIG",
    "DECISION_MEMO_CONFIG",
    "validate_synthesis_for_class",
    "create_pipeline",
    "get_config_for_pipeline",
    # verification
    "VerificationViolation",
    "verify_body_citations",
    "verify_synthesis_citations",
    "verify_export_artifact",
    # export bundle
    "BundleManifest",
    "BundleProvenance",
    "ExportBundle",
    "build_export_bundle",
]
