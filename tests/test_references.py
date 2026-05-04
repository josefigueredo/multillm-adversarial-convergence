"""Unit tests for src.evidence.references — deterministic references assembly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evidence.references import (
    normalize_url,
    dedupe_citations,
    build_references_section,
    inject_references_section,
    generate_references_for_synthesis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cite(url: str, title: str = "", source_type: str = "web") -> dict:
    return {
        "id": "cite-001",
        "url": url,
        "title": title,
        "source_type": source_type,
        "trust_class": "untrusted_web_content",
    }


def _local_cite(path: str) -> dict:
    return {
        "id": "local-001",
        "path": path,
        "source_type": "local_file",
        "trust_class": "user_provided_source_material",
    }


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/path/") == "https://example.com/path"

    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_utm_source(self):
        url = "https://example.com/post?utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_preserves_non_tracking_query_params(self):
        url = "https://arxiv.org/abs/2301.00001?version=2"
        result = normalize_url(url)
        assert "version=2" in result

    def test_lowercases_scheme_and_host(self):
        result = normalize_url("HTTPS://Example.COM/Path")
        assert result.startswith("https://example.com")

    def test_preserves_path_case(self):
        result = normalize_url("https://example.com/My/Path")
        assert "/My/Path" in result

    def test_root_url_trailing_slash_stripped(self):
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_returns_string(self):
        assert isinstance(normalize_url("https://example.com"), str)

    def test_no_change_to_clean_url(self):
        url = "https://docs.example.com/guide"
        assert normalize_url(url) == url


# ---------------------------------------------------------------------------
# dedupe_citations
# ---------------------------------------------------------------------------

class TestDedupeCitations:
    def test_identical_urls_deduped_to_one(self):
        citations = [
            _cite("https://example.com/page", title="First"),
            _cite("https://example.com/page", title="Second"),
        ]
        result = dedupe_citations(citations)
        assert len(result) == 1

    def test_prefers_entry_with_title(self):
        citations = [
            _cite("https://example.com/page", title=""),
            _cite("https://example.com/page", title="Good Title"),
        ]
        result = dedupe_citations(citations)
        assert result[0]["title"] == "Good Title"

    def test_prefers_titled_even_if_second(self):
        citations = [
            _cite("https://example.com/page", title="First Title"),
            _cite("https://example.com/page", title=""),
        ]
        result = dedupe_citations(citations)
        assert result[0]["title"] == "First Title"

    def test_distinct_urls_all_kept(self):
        citations = [
            _cite("https://example.com/a"),
            _cite("https://example.com/b"),
            _cite("https://example.com/c"),
        ]
        result = dedupe_citations(citations)
        assert len(result) == 3

    def test_trailing_slash_deduped(self):
        citations = [
            _cite("https://example.com/page/"),
            _cite("https://example.com/page"),
        ]
        result = dedupe_citations(citations)
        assert len(result) == 1

    def test_local_path_citations_excluded(self):
        citations = [
            _cite("https://example.com/page"),
            _local_cite("/input/spec.pdf"),
        ]
        result = dedupe_citations(citations)
        assert len(result) == 1
        assert result[0].get("url") == "https://example.com/page"

    def test_empty_list_returns_empty(self):
        assert dedupe_citations([]) == []

    def test_all_local_returns_empty(self):
        citations = [_local_cite("/a.pdf"), _local_cite("/b.pdf")]
        result = dedupe_citations(citations)
        assert result == []

    def test_utm_deduped_as_same_url(self):
        citations = [
            _cite("https://example.com/post?utm_source=twitter"),
            _cite("https://example.com/post"),
        ]
        result = dedupe_citations(citations)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# build_references_section
# ---------------------------------------------------------------------------

class TestBuildReferencesSection:
    def test_empty_citations_returns_empty_string(self):
        result = build_references_section([])
        assert result == ""

    def test_returns_string(self):
        result = build_references_section([_cite("https://example.com")])
        assert isinstance(result, str)

    def test_contains_references_heading(self):
        result = build_references_section([_cite("https://example.com")])
        assert "References" in result

    def test_contains_url(self):
        result = build_references_section([_cite("https://example.com/page")])
        assert "https://example.com/page" in result

    def test_uses_title_when_present(self):
        result = build_references_section([_cite("https://example.com", title="My Title")])
        assert "My Title" in result

    def test_uses_url_as_fallback_when_no_title(self):
        result = build_references_section([_cite("https://example.com", title="")])
        assert "example.com" in result

    def test_numbered_list(self):
        citations = [
            _cite("https://a.com", title="A"),
            _cite("https://b.com", title="B"),
        ]
        result = build_references_section(citations)
        assert "1." in result
        assert "2." in result

    def test_local_citations_excluded(self):
        citations = [
            _cite("https://example.com", title="Web page"),
            _local_cite("/input/file.pdf"),
        ]
        result = build_references_section(citations)
        assert "/input/file.pdf" not in result
        assert "example.com" in result

    def test_all_local_citations_returns_empty(self):
        citations = [_local_cite("/a.pdf"), _local_cite("/b.pdf")]
        result = build_references_section(citations)
        assert result == ""

    def test_markdown_link_format(self):
        result = build_references_section([_cite("https://example.com", title="Title")])
        assert "[Title](https://example.com)" in result


# ---------------------------------------------------------------------------
# inject_references_section
# ---------------------------------------------------------------------------

class TestInjectReferencesSection:
    REFS_BLOCK = "## References\n\n1. [Example](https://example.com)\n"

    def test_appends_when_no_existing_references(self):
        md = "# My Paper\n\nSome content.\n"
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "## References" in result
        assert result.endswith("\n")

    def test_replaces_existing_h2_references(self):
        md = "# Paper\n\nContent.\n\n## References\n\n1. [Old](https://old.com)\n"
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "old.com" not in result
        assert "example.com" in result

    def test_replaces_existing_h1_references(self):
        md = "# Paper\n\nContent.\n\n# References\n\n1. [Old](https://old.com)\n"
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "old.com" not in result
        assert "example.com" in result

    def test_replaces_bibliography_heading(self):
        md = "# Paper\n\nContent.\n\n## Bibliography\n\n1. [Old](https://old.com)\n"
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "old.com" not in result
        assert "example.com" in result

    def test_preserves_content_after_references_section(self):
        md = (
            "# Paper\n\nContent.\n\n"
            "## References\n\n1. [Old](https://old.com)\n\n"
            "## Appendix\n\nAppendix content.\n"
        )
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "Appendix content." in result
        assert "old.com" not in result
        assert "example.com" in result

    def test_returns_string(self):
        result = inject_references_section("some text", self.REFS_BLOCK)
        assert isinstance(result, str)

    def test_returns_unchanged_when_refs_block_empty(self):
        md = "# Paper\n\nContent.\n"
        result = inject_references_section(md, "")
        assert result == md

    def test_original_content_preserved(self):
        md = "# Paper\n\nImportant content here.\n"
        result = inject_references_section(md, self.REFS_BLOCK)
        assert "Important content here." in result


# ---------------------------------------------------------------------------
# generate_references_for_synthesis — filesystem integration
# ---------------------------------------------------------------------------

class TestGenerateReferencesForSynthesis:
    def test_injects_references_into_synthesis_file(self, tmp_path):
        synthesis = tmp_path / "synthesis.md"
        synthesis.write_text("# Report\n\nSome content.\n", encoding="utf-8")
        citations = [_cite("https://example.com", title="Example")]
        (tmp_path / "citations.json").write_text(json.dumps(citations), encoding="utf-8")

        generate_references_for_synthesis(synthesis, tmp_path / "citations.json")

        result = synthesis.read_text(encoding="utf-8")
        assert "## References" in result
        assert "example.com" in result

    def test_returns_final_text(self, tmp_path):
        synthesis = tmp_path / "synthesis.md"
        synthesis.write_text("# Report\n\nContent.\n", encoding="utf-8")
        citations = [_cite("https://example.com")]
        (tmp_path / "citations.json").write_text(json.dumps(citations), encoding="utf-8")

        result = generate_references_for_synthesis(synthesis, tmp_path / "citations.json")
        assert isinstance(result, str)
        assert "example.com" in result

    def test_handles_missing_citations_file(self, tmp_path):
        synthesis = tmp_path / "synthesis.md"
        synthesis.write_text("# Report\n\nContent.\n", encoding="utf-8")

        # Should not raise — returns original text unchanged
        result = generate_references_for_synthesis(synthesis, tmp_path / "citations.json")
        assert result == "# Report\n\nContent.\n"

    def test_handles_missing_synthesis_file(self, tmp_path):
        citations = [_cite("https://example.com")]
        (tmp_path / "citations.json").write_text(json.dumps(citations), encoding="utf-8")

        # Should not raise — returns empty string
        result = generate_references_for_synthesis(
            tmp_path / "synthesis.md", tmp_path / "citations.json"
        )
        assert result == ""

    def test_dedupes_citations_in_output(self, tmp_path):
        synthesis = tmp_path / "synthesis.md"
        synthesis.write_text("# Report\n\nContent.\n", encoding="utf-8")
        citations = [
            _cite("https://example.com/page/", title="First"),
            _cite("https://example.com/page", title="Second"),
        ]
        (tmp_path / "citations.json").write_text(json.dumps(citations), encoding="utf-8")

        generate_references_for_synthesis(synthesis, tmp_path / "citations.json")
        result = synthesis.read_text(encoding="utf-8")
        # Should only appear once
        assert result.count("example.com/page") == 1

    def test_replaces_existing_references_section(self, tmp_path):
        synthesis = tmp_path / "synthesis.md"
        synthesis.write_text(
            "# Report\n\nContent.\n\n## References\n\n1. [Old](https://old.com)\n",
            encoding="utf-8",
        )
        citations = [_cite("https://new.com", title="New Source")]
        (tmp_path / "citations.json").write_text(json.dumps(citations), encoding="utf-8")

        generate_references_for_synthesis(synthesis, tmp_path / "citations.json")
        result = synthesis.read_text(encoding="utf-8")
        assert "old.com" not in result
        assert "new.com" in result


# ---------------------------------------------------------------------------
# Orchestrator integration — synthesis gains deterministic references
# ---------------------------------------------------------------------------

class TestOrchestratorReferencesIntegration:
    """Prove _inject_deterministic_references is wired into _generate_synthesis."""

    def _make_researcher_with_citations(
        self, tmp_path, citations: list[dict], output_style: str = "paper"
    ):
        """Return a minimal AutoResearcher with pre-loaded citations."""
        from unittest.mock import MagicMock
        from src.config import (
            BackendsConfig, ExecutionConfig, ReportingConfig, ResearchConfig, ScoringConfig,
        )
        from src.orchestrator import AutoResearcher

        config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("dim1",),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
            ),
            scoring=ScoringConfig(),
            reporting=ReportingConfig(output_style=output_style),
        )
        backend = MagicMock()
        backend.name = "claude-cli"
        backend.supports_tools = False
        researcher = AutoResearcher(config, backend, tmp_path)
        researcher._citations = list(citations)
        return researcher

    def test_inject_deterministic_references_returns_text_with_refs(self, tmp_path):
        researcher = self._make_researcher_with_citations(tmp_path, [
            _cite("https://example.com", title="Test Source"),
        ], output_style="paper")
        synthesis_text = "# Report\n\nSome synthesis content.\n"
        result = researcher._inject_deterministic_references(synthesis_text)
        assert "References" in result
        assert "example.com" in result

    def test_inject_skipped_for_non_paper_style(self, tmp_path):
        """Non-paper output styles must NOT receive an auto-injected References block."""
        for style in ("default", "technical_doc", "executive_brief", "decision_memo"):
            researcher = self._make_researcher_with_citations(tmp_path, [
                _cite("https://example.com", title="Test Source"),
            ], output_style=style)
            synthesis_text = "# Report\n\nContent.\n"
            result = researcher._inject_deterministic_references(synthesis_text)
            assert result == synthesis_text, (
                f"Style '{style}' should not inject references, but got:\n{result}"
            )

    def test_inject_returns_original_when_no_url_citations(self, tmp_path):
        researcher = self._make_researcher_with_citations(tmp_path, [
            _local_cite("/input/spec.pdf"),
        ], output_style="paper")
        synthesis_text = "# Report\n\nContent.\n"
        result = researcher._inject_deterministic_references(synthesis_text)
        assert result == synthesis_text

    def test_resume_loads_existing_citations(self, tmp_path):
        """_resume() must restore citations.json into self._citations."""
        from unittest.mock import MagicMock
        import json as _json
        from src.config import (
            BackendsConfig, ExecutionConfig, ResearchConfig, ScoringConfig,
        )
        from src.orchestrator import AutoResearcher

        # Write minimal iteration state so _resume() finds something to load
        iterations_dir = tmp_path / "iterations"
        iterations_dir.mkdir()
        (iterations_dir / "iter_001.md").write_text("# Iter\n\nfindings.", encoding="utf-8")
        (tmp_path / "results.tsv").write_text("dim\tscore\t1\tfinding\n", encoding="utf-8")
        (tmp_path / "knowledge_base.md").write_text("KB content", encoding="utf-8")

        # Write existing citations.json (as if from a prior run)
        prior_citations = [_cite("https://prior.com", title="Prior Source")]
        (tmp_path / "citations.json").write_text(
            _json.dumps(prior_citations), encoding="utf-8"
        )

        config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("dim1",),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
            ),
            scoring=ScoringConfig(),
        )
        backend = MagicMock()
        backend.name = "claude-cli"
        backend.supports_tools = False
        researcher = AutoResearcher(config, backend, tmp_path)

        # Before resume, _citations should be empty
        assert researcher._citations == []

        researcher._resume()

        # After resume, citations from citations.json should be loaded
        assert len(researcher._citations) > 0
        urls = [c.get("url") for c in researcher._citations]
        assert "https://prior.com" in urls
