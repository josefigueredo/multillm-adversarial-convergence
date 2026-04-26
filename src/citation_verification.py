"""Citation and export verification — MM11 Step 3.

Provides structured coverage checks over:

- **Citation presence** — when a deliverable class requires citations,
  the synthesis body must contain a proper Markdown ``References`` or
  ``Bibliography`` heading with at least one numbered entry beneath it.
- **Export readiness** — an :class:`~src.deliverable_pipeline.ExportArtifact`
  must have non-blank output paths and a well-formed ISO 8601 timestamp.

Both checkers return a list of :class:`VerificationViolation` objects so
callers can report, log, or block pipeline advancement as appropriate.

The citation heading regex is shared with :mod:`src.references` via
:data:`~src.references.REFS_HEADING_RE` to ensure generation and
verification cannot drift from each other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .deliverable_classes import DeliverableClassConfig
from .deliverable_pipeline import ExportArtifact, SynthesisArtifact
from .references import REFS_HEADING_RE

# Matches a numbered citation entry: "1. ..." (with optional leading whitespace)
_CITATION_ENTRY_RE = re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE)

# Minimum ISO 8601 shape: YYYY-MM-DD (optionally followed by time/zone info)
_ISO8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# VerificationViolation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationViolation:
    """A single violation found during citation or export verification.

    Attributes
    ----------
    code:
        Machine-readable identifier, e.g. ``"missing_references_section"``.
    message:
        Human-readable description suitable for logs and reports.
    """

    code: str
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_section_body(markdown: str, heading_match: re.Match) -> str:  # type: ignore[type-arg]
    """Return the content between *heading_match* and the next same-or-higher heading."""
    heading_level = len(heading_match.group(0).split()[0])  # count '#' chars
    after = markdown[heading_match.end():]
    next_heading_re = re.compile(
        r"^#{1," + str(heading_level) + r"}\s+\S",
        re.MULTILINE,
    )
    next_match = next_heading_re.search(after)
    return after[: next_match.start()] if next_match else after


# ---------------------------------------------------------------------------
# Citation verification
# ---------------------------------------------------------------------------


def verify_synthesis_citations(
    synthesis: SynthesisArtifact,
    config: DeliverableClassConfig,
) -> list[VerificationViolation]:
    """Return violations for *synthesis* based on citation requirements in *config*.

    When ``config.requires_citations`` is ``False``, the check is a no-op and
    always returns an empty list.

    When ``True``, two things are checked:

    1. A Markdown ``## References`` or ``## Bibliography`` heading (any level
       1-6) must appear in the synthesis body.
    2. The section under that heading must contain at least one numbered entry
       of the form ``N. <non-whitespace>``.  Numbered entries in sections that
       follow the References heading (e.g. an Appendix) are not counted.
    """
    if not config.requires_citations:
        return []

    match = REFS_HEADING_RE.search(synthesis.body)
    if not match:
        return [
            VerificationViolation(
                code="missing_references_section",
                message="synthesis body is missing a References or Bibliography heading",
            )
        ]

    section = _extract_section_body(synthesis.body, match)
    if not _CITATION_ENTRY_RE.search(section):
        return [
            VerificationViolation(
                code="empty_references_section",
                message="References section exists but contains no numbered citation entries",
            )
        ]

    return []


# ---------------------------------------------------------------------------
# Export verification
# ---------------------------------------------------------------------------


def verify_export_artifact(export: ExportArtifact) -> list[VerificationViolation]:
    """Return violations for *export* based on publication packaging requirements.

    Checks performed:

    - ``output_paths`` must be non-empty.
    - No path in ``output_paths`` may be blank (empty or whitespace-only).
    - ``exported_at`` must be non-empty and match the ISO 8601
      date format (at minimum ``YYYY-MM-DD``).
    """
    violations: list[VerificationViolation] = []

    if not export.output_paths:
        violations.append(
            VerificationViolation(
                code="no_output_paths",
                message="ExportArtifact has no output paths",
            )
        )
    else:
        for path in export.output_paths:
            if not path.strip():
                violations.append(
                    VerificationViolation(
                        code="empty_output_path",
                        message="ExportArtifact contains a blank output path",
                    )
                )
                break  # one violation is enough; caller can iterate paths if needed

    exported_at = export.exported_at.strip()
    if not exported_at:
        violations.append(
            VerificationViolation(
                code="missing_exported_at",
                message="ExportArtifact.exported_at is empty or whitespace",
            )
        )
    elif not _ISO8601_RE.match(exported_at):
        violations.append(
            VerificationViolation(
                code="invalid_exported_at",
                message=(
                    f"ExportArtifact.exported_at does not look like an ISO 8601 "
                    f"timestamp: {export.exported_at!r}"
                ),
            )
        )

    return violations
