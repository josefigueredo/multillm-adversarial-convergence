"""Unit tests for src.trust — trust classification model."""

from __future__ import annotations

from src.policy.trust import (
    TRUST_CLASSES,
    classify_citation_trust,
    classify_claim_trust,
    trust_summary,
)


# ---------------------------------------------------------------------------
# Trust class constants
# ---------------------------------------------------------------------------

class TestTrustClasses:
    def test_trust_classes_is_frozenset(self):
        assert isinstance(TRUST_CLASSES, frozenset)

    def test_all_expected_classes_present(self):
        expected = {
            "trusted_local_config",
            "trusted_generated_artifact",
            "untrusted_web_content",
            "untrusted_tool_output",
            "user_provided_source_material",
            "inferred_claim",
        }
        assert expected <= TRUST_CLASSES

    def test_no_extra_classes(self):
        # Keeps the surface area intentional
        assert len(TRUST_CLASSES) == 6


# ---------------------------------------------------------------------------
# Citation trust classification
# ---------------------------------------------------------------------------

class TestClassifyCitationTrust:
    def _citation(self, source_type: str = "web") -> dict:
        return {"url": "https://example.com", "source_type": source_type}

    def _local_citation(self, path: str = "/docs/spec.pdf") -> dict:
        return {"path": path, "source_type": "local_file"}

    def test_web_citation_is_untrusted_web_content(self):
        assert classify_citation_trust(self._citation("web")) == "untrusted_web_content"

    def test_official_docs_citation_is_untrusted_web_content(self):
        # High quality ≠ trusted origin — it's still fetched from the web
        assert classify_citation_trust(self._citation("official_docs")) == "untrusted_web_content"

    def test_paper_citation_is_untrusted_web_content(self):
        assert classify_citation_trust(self._citation("paper")) == "untrusted_web_content"

    def test_repository_citation_is_untrusted_web_content(self):
        assert classify_citation_trust(self._citation("repository")) == "untrusted_web_content"

    def test_community_citation_is_untrusted_web_content(self):
        assert classify_citation_trust(self._citation("community")) == "untrusted_web_content"

    def test_local_path_citation_is_user_provided_source_material(self):
        assert classify_citation_trust(self._local_citation()) == "user_provided_source_material"

    def test_local_path_without_url_is_user_provided(self):
        result = classify_citation_trust({"path": "/input/prd.md", "source_type": "local_file"})
        assert result == "user_provided_source_material"

    def test_record_with_both_url_and_path_is_untrusted_web(self):
        # URL takes precedence — if there's a URL it's a web fetch
        result = classify_citation_trust({"url": "https://example.com", "path": "/also/local.pdf"})
        assert result == "untrusted_web_content"

    def test_result_is_a_valid_trust_class(self):
        result = classify_citation_trust(self._citation())
        assert result in TRUST_CLASSES

    def test_local_result_is_a_valid_trust_class(self):
        result = classify_citation_trust(self._local_citation())
        assert result in TRUST_CLASSES

    def test_missing_source_type_still_returns_valid_class(self):
        result = classify_citation_trust({"url": "https://example.com"})
        assert result in TRUST_CLASSES


# ---------------------------------------------------------------------------
# Claim trust classification
# ---------------------------------------------------------------------------

class TestClassifyClaimTrust:
    def _claim(self, claim_type: str = "factual", text: str = "some long claim text here") -> dict:
        return {"text": text, "claim_type": claim_type}

    def test_factual_claim_is_inferred_claim(self):
        assert classify_claim_trust(self._claim("factual")) == "inferred_claim"

    def test_recommendation_claim_is_inferred_claim(self):
        assert classify_claim_trust(self._claim("recommendation")) == "inferred_claim"

    def test_interpretive_claim_is_inferred_claim(self):
        assert classify_claim_trust(self._claim("interpretive")) == "inferred_claim"

    def test_unlabeled_claim_is_inferred_claim(self):
        assert classify_claim_trust(self._claim("unlabeled")) == "inferred_claim"

    def test_result_is_a_valid_trust_class(self):
        result = classify_claim_trust(self._claim())
        assert result in TRUST_CLASSES

    def test_missing_claim_type_still_returns_valid_class(self):
        result = classify_claim_trust({"text": "some claim text"})
        assert result in TRUST_CLASSES


# ---------------------------------------------------------------------------
# Trust summary aggregation
# ---------------------------------------------------------------------------

class TestTrustSummary:
    def test_empty_list_returns_empty_dict(self):
        assert trust_summary([]) == {}

    def test_single_class_counted(self):
        items = [
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "untrusted_web_content"},
        ]
        result = trust_summary(items)
        assert result == {"untrusted_web_content": 3}

    def test_mixed_classes_counted(self):
        items = [
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "inferred_claim"},
        ]
        result = trust_summary(items)
        assert result["untrusted_web_content"] == 2
        assert result["inferred_claim"] == 1

    def test_items_without_trust_class_skipped(self):
        items = [
            {"trust_class": "inferred_claim"},
            {"no_trust_class": "here"},
        ]
        result = trust_summary(items)
        assert result == {"inferred_claim": 1}

    def test_returns_dict(self):
        result = trust_summary([{"trust_class": "inferred_claim"}])
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Provenance integration — extract_citations gains trust_class
# ---------------------------------------------------------------------------

class TestProvenanceCitationIntegration:
    def test_extract_citations_adds_trust_class(self):
        from src.provenance import extract_citations

        text = "See [example](https://example.com) for details."
        cits = extract_citations(text, scope="test", retrieved_at="2024-01-01")
        assert len(cits) >= 1
        for c in cits:
            assert "trust_class" in c

    def test_extract_citations_trust_class_is_untrusted_web_content(self):
        from src.provenance import extract_citations

        text = "See [example](https://example.com) for details."
        cits = extract_citations(text, scope="test", retrieved_at="2024-01-01")
        for c in cits:
            assert c["trust_class"] == "untrusted_web_content"

    def test_extract_citations_trust_class_is_valid(self):
        from src.provenance import extract_citations

        text = "Reference: https://arxiv.org/abs/2301.00001"
        cits = extract_citations(text, scope="test", retrieved_at="2024-01-01")
        for c in cits:
            assert c["trust_class"] in TRUST_CLASSES


# ---------------------------------------------------------------------------
# Provenance integration — extract_claims gains trust_class
# ---------------------------------------------------------------------------

class TestProvenanceClaimIntegration:
    LONG_CLAIM = (
        "Redis consistently outperforms Memcached for complex data structures "
        "because it supports native data types like hashes, sets, and sorted sets."
    )

    def test_extract_claims_adds_trust_class(self):
        from src.provenance import extract_claims

        claims = extract_claims(self.LONG_CLAIM, scope="test")
        assert len(claims) >= 1
        for c in claims:
            assert "trust_class" in c

    def test_extract_claims_trust_class_is_inferred_claim(self):
        from src.provenance import extract_claims

        claims = extract_claims(self.LONG_CLAIM, scope="test")
        for c in claims:
            assert c["trust_class"] == "inferred_claim"

    def test_extract_claims_trust_class_is_valid(self):
        from src.provenance import extract_claims

        claims = extract_claims(self.LONG_CLAIM, scope="test")
        for c in claims:
            assert c["trust_class"] in TRUST_CLASSES


# ---------------------------------------------------------------------------
# Dashboard integration — trust_summary in dashboard_payload
# ---------------------------------------------------------------------------

class TestDashboardTrustSummary:
    def _minimal_dashboard_kwargs(self) -> dict:
        return dict(
            topic="Test topic",
            goal="Test goal",
            benchmark_id="bench-1",
            current_strategy="single",
            output_style="research_paper",
            output_style_label="Research Paper",
            active_style_overrides=None,
            best_score=0.75,
            iteration=3,
            explored_dimensions=["dim1", "dim2"],
            rubric={},
            evidence_quality={},
            comparison={},
            evaluation={},
            strategy_summary={},
            semantic_calibration={},
            semantic_review={},
        )

    def test_dashboard_payload_includes_trust_summary_when_provided(self):
        from src.artifacts import dashboard_payload

        summary = {"untrusted_web_content": 10, "inferred_claim": 5}
        result = dashboard_payload(**self._minimal_dashboard_kwargs(), trust_summary=summary)
        assert "trust_summary" in result
        assert result["trust_summary"] == summary

    def test_dashboard_payload_trust_summary_defaults_to_empty(self):
        from src.artifacts import dashboard_payload

        result = dashboard_payload(**self._minimal_dashboard_kwargs())
        # trust_summary key exists and is a dict (may be empty)
        assert "trust_summary" in result
        assert isinstance(result["trust_summary"], dict)


# ---------------------------------------------------------------------------
# build_source_file_provenance
# ---------------------------------------------------------------------------

class FakeSourceFile:
    """Minimal SourceFileConfig-like for testing."""

    def __init__(self, path: str, roles: tuple[str, ...] = ("builder",)) -> None:
        self.path = path
        self.roles = roles


class TestBuildSourceFileProvenance:
    def test_returns_list(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/docs/spec.pdf")])
        assert isinstance(result, list)

    def test_one_record_per_source_file(self):
        from src.provenance import build_source_file_provenance

        files = [FakeSourceFile("/a.pdf"), FakeSourceFile("/b.md")]
        result = build_source_file_provenance(files)
        assert len(result) == 2

    def test_each_record_has_trust_class(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/docs/spec.pdf")])
        for record in result:
            assert "trust_class" in record

    def test_trust_class_is_user_provided_source_material(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/docs/spec.pdf")])
        for record in result:
            assert record["trust_class"] == "user_provided_source_material"

    def test_records_have_path_field(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/docs/spec.pdf")])
        assert result[0]["path"] == "/docs/spec.pdf"

    def test_records_have_source_type_local_file(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/docs/spec.pdf")])
        assert result[0]["source_type"] == "local_file"

    def test_empty_source_files_returns_empty_list(self):
        from src.provenance import build_source_file_provenance

        assert build_source_file_provenance([]) == []

    def test_trust_class_is_valid(self):
        from src.provenance import build_source_file_provenance

        result = build_source_file_provenance([FakeSourceFile("/x.pdf")])
        assert result[0]["trust_class"] in TRUST_CLASSES


# ---------------------------------------------------------------------------
# Real integrated path: local source → citations.json → write_dashboard →
# dashboard.json trust_summary contains user_provided_source_material
# ---------------------------------------------------------------------------

class TestLocalSourceTrustIntegration:
    def _minimal_config(self):
        from src.config import (
            BackendsConfig, ExecutionConfig, ResearchConfig, ScoringConfig,
        )
        return ResearchConfig(
            topic="Integration test",
            goal="Verify trust flows through dashboard",
            dimensions=("dim1",),
            execution=ExecutionConfig(
                backend="claude-cli",
                backends=BackendsConfig(primary="claude-cli"),
                allowed_tools="WebSearch",
            ),
            scoring=ScoringConfig(),
        )

    def test_local_source_records_in_citations_appear_in_dashboard_trust_summary(self, tmp_path):
        import json
        from src.artifacts import write_dashboard
        from src.provenance import build_source_file_provenance

        # Build local source provenance records
        records = build_source_file_provenance([
            FakeSourceFile("/input/prd.md", roles=("builder",)),
            FakeSourceFile("/input/spec.pdf", roles=("builder", "challenger")),
        ])

        # Write citations.json to the output dir (as orchestrator would)
        (tmp_path / "citations.json").write_text(json.dumps(records), encoding="utf-8")

        # write_dashboard loads citations.json and computes trust_summary
        config = self._minimal_config()
        write_dashboard(
            tmp_path,
            config=config,
            best_score=0.0,
            iteration=0,
            explored_dimensions=[],
        )

        dashboard = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
        assert "trust_summary" in dashboard
        assert dashboard["trust_summary"].get("user_provided_source_material", 0) == 2

    def test_mixed_local_and_url_citations_both_appear_in_trust_summary(self, tmp_path):
        import json
        from src.artifacts import write_dashboard
        from src.provenance import build_source_file_provenance, extract_citations

        local_records = build_source_file_provenance([FakeSourceFile("/input/doc.md")])
        url_records = extract_citations(
            "See [example](https://example.com) for details.",
            scope="test",
            retrieved_at="2024-01-01",
        )
        all_records = local_records + url_records
        (tmp_path / "citations.json").write_text(json.dumps(all_records), encoding="utf-8")

        config = self._minimal_config()
        write_dashboard(
            tmp_path,
            config=config,
            best_score=0.0,
            iteration=0,
            explored_dimensions=[],
        )

        dashboard = json.loads((tmp_path / "dashboard.json").read_text(encoding="utf-8"))
        summary = dashboard["trust_summary"]
        assert summary.get("user_provided_source_material", 0) >= 1
        assert summary.get("untrusted_web_content", 0) >= 1

