"""Deliverable class pipelines — MM11 Step 2.

Adds class-specific pipeline configuration on top of the shared
:class:`~src.deliverable_pipeline.DeliverablePipeline` model from Step 1.

Four deliverable classes are supported:

- **paper** — academic/research paper (LaTeX, citations required, multi-section)
- **technical_doc** — technical documentation (Markdown, structured API/usage sections)
- **executive_brief** — short executive summary (Markdown, word-limited, no citations)
- **decision_memo** — action-oriented memo (Markdown, recommendation + rationale)

Each class ships with a pre-built :class:`DeliverableClassConfig` that
encodes its default format, required sections, word limits, and citation
requirements.  Use :func:`create_pipeline` to get a fresh
:class:`~src.deliverable_pipeline.DeliverablePipeline` for a given class, and
:func:`validate_synthesis_for_class` to check a synthesis artifact against
class-specific constraints before advancing the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .deliverable_pipeline import DeliverablePipeline, SynthesisArtifact


# ---------------------------------------------------------------------------
# DeliverableClass
# ---------------------------------------------------------------------------

class DeliverableClass(str, Enum):
    """The four supported deliverable output classes."""

    PAPER = "paper"
    TECHNICAL_DOC = "technical_doc"
    EXECUTIVE_BRIEF = "executive_brief"
    DECISION_MEMO = "decision_memo"


# ---------------------------------------------------------------------------
# DeliverableClassConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeliverableClassConfig:
    """Class-specific pipeline configuration.

    Attributes
    ----------
    deliverable_class:
        Which deliverable class this config belongs to.
    default_format:
        Default :attr:`~src.deliverable_pipeline.PackageArtifact.format`
        for this class (e.g. ``"latex"`` or ``"markdown"``).
    required_sections:
        Section identifiers that must appear somewhere in the synthesis body.
        Matched case-insensitively.
    max_body_words:
        Optional upper limit on the synthesis body word count.  ``None``
        means no limit.
    requires_citations:
        Whether this class mandates a citations/references section.
    default_revision_cycles:
        Expected number of revision passes for this class.
    """

    deliverable_class: DeliverableClass
    default_format: str
    required_sections: tuple[str, ...]
    max_body_words: int | None = None
    requires_citations: bool = False
    default_revision_cycles: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "deliverable_class": self.deliverable_class.value,
            "default_format": self.default_format,
            "required_sections": list(self.required_sections),
            "max_body_words": self.max_body_words,
            "requires_citations": self.requires_citations,
            "default_revision_cycles": self.default_revision_cycles,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DeliverableClassConfig":
        return cls(
            deliverable_class=DeliverableClass(d["deliverable_class"]),
            default_format=d["default_format"],
            required_sections=tuple(d["required_sections"]),
            max_body_words=d.get("max_body_words"),
            requires_citations=bool(d.get("requires_citations", False)),
            default_revision_cycles=int(d.get("default_revision_cycles", 1)),
        )


# ---------------------------------------------------------------------------
# Pre-built configs
# ---------------------------------------------------------------------------

PAPER_CONFIG = DeliverableClassConfig(
    deliverable_class=DeliverableClass.PAPER,
    default_format="latex",
    required_sections=(
        "abstract",
        "introduction",
        "methodology",
        "results",
        "conclusion",
    ),
    max_body_words=None,
    requires_citations=True,
    default_revision_cycles=2,
)

TECHNICAL_DOC_CONFIG = DeliverableClassConfig(
    deliverable_class=DeliverableClass.TECHNICAL_DOC,
    default_format="markdown",
    required_sections=(
        "overview",
        "installation",
        "usage",
        "api_reference",
    ),
    max_body_words=None,
    requires_citations=False,
    default_revision_cycles=1,
)

EXECUTIVE_BRIEF_CONFIG = DeliverableClassConfig(
    deliverable_class=DeliverableClass.EXECUTIVE_BRIEF,
    default_format="markdown",
    required_sections=(
        "key_takeaways",
        "recommendations",
    ),
    max_body_words=500,
    requires_citations=False,
    default_revision_cycles=1,
)

DECISION_MEMO_CONFIG = DeliverableClassConfig(
    deliverable_class=DeliverableClass.DECISION_MEMO,
    default_format="markdown",
    required_sections=(
        "recommendation",
        "rationale",
        "alternatives",
        "risks",
    ),
    max_body_words=1000,
    requires_citations=False,
    default_revision_cycles=1,
)

#: Registry from deliverable class to its config.
CLASS_CONFIGS: dict[DeliverableClass, DeliverableClassConfig] = {
    DeliverableClass.PAPER: PAPER_CONFIG,
    DeliverableClass.TECHNICAL_DOC: TECHNICAL_DOC_CONFIG,
    DeliverableClass.EXECUTIVE_BRIEF: EXECUTIVE_BRIEF_CONFIG,
    DeliverableClass.DECISION_MEMO: DECISION_MEMO_CONFIG,
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def validate_synthesis_for_class(
    synthesis: SynthesisArtifact,
    config: DeliverableClassConfig,
) -> list[str]:
    """Return a list of violation messages for *synthesis* against *config*.

    An empty list means the synthesis is valid for this deliverable class.

    Checks performed:
    - Each entry in ``config.required_sections`` must appear in the body
      (case-insensitive, underscore/space normalised).
    - If ``config.max_body_words`` is set, the body word count must not
      exceed it.
    """
    violations: list[str] = []
    body_lower = synthesis.body.lower()

    for section in config.required_sections:
        # normalise underscore → space for flexible matching
        needle = section.replace("_", " ")
        if needle not in body_lower and section not in body_lower:
            violations.append(f"missing required section: {section}")

    if config.max_body_words is not None:
        wc = _word_count(synthesis.body)
        if wc > config.max_body_words:
            violations.append(
                f"body exceeds {config.max_body_words} word limit ({wc} words)"
            )

    return violations


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_pipeline(topic: str, deliverable_class: DeliverableClass) -> DeliverablePipeline:
    """Return a fresh :class:`~src.deliverable_pipeline.DeliverablePipeline` for *topic*.

    The returned pipeline starts at ``PipelineStage.PENDING`` and carries
    the deliverable class identity in
    :attr:`~src.deliverable_pipeline.DeliverablePipeline.deliverable_class`
    so later stages can retrieve the governing config without re-supplying
    the class externally.
    """
    return DeliverablePipeline(topic=topic, deliverable_class=deliverable_class.value)


def get_config_for_pipeline(pipeline: DeliverablePipeline) -> DeliverableClassConfig | None:
    """Return the :class:`DeliverableClassConfig` associated with *pipeline*.

    Returns ``None`` if the pipeline was not created with a deliverable class
    (e.g., constructed directly with ``DeliverablePipeline(topic=...)``).
    """
    if pipeline.deliverable_class is None:
        return None
    return CLASS_CONFIGS[DeliverableClass(pipeline.deliverable_class)]
