"""TDD tests for MM11 Step 3 — citation/export verification.

All tests are written before the implementation exists.
"""

import pytest

from src.deliverable_pipeline import ExportArtifact, SynthesisArtifact
from src.deliverable_classes import (
    DECISION_MEMO_CONFIG,
    EXECUTIVE_BRIEF_CONFIG,
    PAPER_CONFIG,
    TECHNICAL_DOC_CONFIG,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthesis(body: str) -> SynthesisArtifact:
    return SynthesisArtifact(title="T", body=body)


def _export(output_paths: tuple[str, ...] = ("out/paper.pdf",), exported_at: str = "2024-06-01T12:00:00Z") -> ExportArtifact:
    return ExportArtifact(output_paths=output_paths, exported_at=exported_at)


# ---------------------------------------------------------------------------
# verify_synthesis_citations — no citations required
# ---------------------------------------------------------------------------

class TestVerifySynthesisCitationsNotRequired:
    """When requires_citations is False the check is always a no-op."""

    def test_no_citations_required_empty_body(self):
        from src.citation_verification import verify_synthesis_citations
        assert verify_synthesis_citations(_synthesis(""), EXECUTIVE_BRIEF_CONFIG) == []

    def test_no_citations_required_body_with_no_refs(self):
        from src.citation_verification import verify_synthesis_citations
        assert verify_synthesis_citations(_synthesis("Key takeaways here. Recommendations too."), EXECUTIVE_BRIEF_CONFIG) == []

    def test_no_citations_required_technical_doc(self):
        from src.citation_verification import verify_synthesis_citations
        body = "## Overview\nContent\n## Installation\nSteps"
        assert verify_synthesis_citations(_synthesis(body), TECHNICAL_DOC_CONFIG) == []

    def test_no_citations_required_decision_memo(self):
        from src.citation_verification import verify_synthesis_citations
        body = "Recommendation: do X. Rationale: because Y."
        assert verify_synthesis_citations(_synthesis(body), DECISION_MEMO_CONFIG) == []


# ---------------------------------------------------------------------------
# verify_synthesis_citations — citations required, passing cases
# ---------------------------------------------------------------------------

class TestVerifySynthesisCitationsRequired:
    """PAPER_CONFIG requires_citations=True."""

    def _paper_body_with_refs(self, entries: str = "1. [Some Paper](https://example.com)") -> str:
        return (
            "## Abstract\nContent.\n\n"
            "## Introduction\nIntro.\n\n"
            "## References\n\n"
            + entries
        )

    def test_paper_with_numbered_link_citation_passes(self):
        from src.citation_verification import verify_synthesis_citations
        assert verify_synthesis_citations(_synthesis(self._paper_body_with_refs()), PAPER_CONFIG) == []

    def test_paper_with_numbered_plain_url_passes(self):
        from src.citation_verification import verify_synthesis_citations
        body = self._paper_body_with_refs("1. https://example.com/paper.pdf")
        assert verify_synthesis_citations(_synthesis(body), PAPER_CONFIG) == []

    def test_paper_with_bibliography_heading_passes(self):
        from src.citation_verification import verify_synthesis_citations
        body = (
            "## Introduction\nText.\n\n"
            "# Bibliography\n\n"
            "1. Some entry here\n"
        )
        assert verify_synthesis_citations(_synthesis(body), PAPER_CONFIG) == []

    def test_paper_with_multiple_entries_passes(self):
        from src.citation_verification import verify_synthesis_citations
        entries = "1. [A](https://a.com)\n2. [B](https://b.com)\n3. [C](https://c.com)\n"
        assert verify_synthesis_citations(_synthesis(self._paper_body_with_refs(entries)), PAPER_CONFIG) == []

    def test_case_insensitive_references_heading_passes(self):
        from src.citation_verification import verify_synthesis_citations
        body = "## Introduction\nText.\n\n## REFERENCES\n\n1. foo\n"
        assert verify_synthesis_citations(_synthesis(body), PAPER_CONFIG) == []


# ---------------------------------------------------------------------------
# verify_synthesis_citations — citations required, failing cases
# ---------------------------------------------------------------------------

class TestVerifySynthesisCitationsFailures:
    def test_no_references_section_returns_violation(self):
        from src.citation_verification import verify_synthesis_citations
        body = "## Abstract\nContent with no reference list at all."
        violations = verify_synthesis_citations(_synthesis(body), PAPER_CONFIG)
        assert len(violations) == 1
        assert violations[0].code == "missing_references_section"

    def test_prose_containing_word_references_not_a_heading(self):
        from src.citation_verification import verify_synthesis_citations
        body = "See references for details. The references are listed below but not in a heading."
        violations = verify_synthesis_citations(_synthesis(body), PAPER_CONFIG)
        assert any(v.code == "missing_references_section" for v in violations)

    def test_empty_references_section_returns_violation(self):
        from src.citation_verification import verify_synthesis_citations
        body = "## Introduction\nText.\n\n## References\n\n"
        violations = verify_synthesis_citations(_synthesis(body), PAPER_CONFIG)
        assert len(violations) == 1
        assert violations[0].code == "empty_references_section"

    def test_references_section_only_whitespace_returns_violation(self):
        from src.citation_verification import verify_synthesis_citations
        body = "## Introduction\nText.\n\n## References\n\n   \n   \n"
        violations = verify_synthesis_citations(_synthesis(body), PAPER_CONFIG)
        assert any(v.code == "empty_references_section" for v in violations)

    def test_appendix_entries_not_counted_for_empty_references(self):
        """Numbered entries in a section AFTER References do not satisfy it."""
        from src.citation_verification import verify_synthesis_citations
        body = (
            "## Introduction\nText.\n\n"
            "## References\n\n"
            "## Appendix\n\n"
            "1. This is in the appendix, not refs\n"
        )
        violations = verify_synthesis_citations(_synthesis(body), PAPER_CONFIG)
        assert any(v.code == "empty_references_section" for v in violations)

    def test_violation_message_is_non_empty(self):
        from src.citation_verification import verify_synthesis_citations
        violations = verify_synthesis_citations(_synthesis("No refs here."), PAPER_CONFIG)
        assert violations[0].message


# ---------------------------------------------------------------------------
# verify_export_artifact — passing cases
# ---------------------------------------------------------------------------

class TestVerifyExportArtifactPassing:
    def test_valid_export_no_violations(self):
        from src.citation_verification import verify_export_artifact
        assert verify_export_artifact(_export()) == []

    def test_multiple_output_paths_accepted(self):
        from src.citation_verification import verify_export_artifact
        e = _export(output_paths=("out/paper.pdf", "out/paper.tex"), exported_at="2024-01-01T00:00:00")
        assert verify_export_artifact(e) == []

    def test_iso8601_date_only_accepted(self):
        from src.citation_verification import verify_export_artifact
        e = _export(exported_at="2024-06-15")
        assert verify_export_artifact(e) == []

    def test_iso8601_with_offset_accepted(self):
        from src.citation_verification import verify_export_artifact
        e = _export(exported_at="2024-06-15T12:00:00+03:00")
        assert verify_export_artifact(e) == []


# ---------------------------------------------------------------------------
# verify_export_artifact — failing cases
# ---------------------------------------------------------------------------

class TestVerifyExportArtifactFailures:
    def test_empty_output_paths_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(output_paths=()))
        assert any(v.code == "no_output_paths" for v in violations)

    def test_blank_path_in_output_paths_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(output_paths=("   ",)))
        assert any(v.code == "empty_output_path" for v in violations)

    def test_empty_string_path_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(output_paths=("",)))
        assert any(v.code == "empty_output_path" for v in violations)

    def test_empty_exported_at_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(exported_at=""))
        assert any(v.code == "missing_exported_at" for v in violations)

    def test_whitespace_only_exported_at_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(exported_at="   "))
        assert any(v.code == "missing_exported_at" for v in violations)

    def test_non_iso8601_exported_at_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(exported_at="June 1st 2024"))
        assert any(v.code == "invalid_exported_at" for v in violations)

    def test_random_string_exported_at_returns_violation(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(_export(exported_at="not-a-date"))
        assert any(v.code == "invalid_exported_at" for v in violations)

    def test_both_missing_paths_and_exported_at_returns_two_violations(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(ExportArtifact(output_paths=(), exported_at=""))
        codes = {v.code for v in violations}
        assert "no_output_paths" in codes
        assert "missing_exported_at" in codes

    def test_all_violations_have_non_empty_messages(self):
        from src.citation_verification import verify_export_artifact
        violations = verify_export_artifact(ExportArtifact(output_paths=(), exported_at=""))
        assert all(v.message for v in violations)
