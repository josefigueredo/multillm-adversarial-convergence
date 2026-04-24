"""Unit tests for src.trust — trust classification model."""

from __future__ import annotations

from src.trust import (
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

    def test_result_is_a_valid_trust_class(self):
        result = classify_citation_trust(self._citation())
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
