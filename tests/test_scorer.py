"""Tests for src.scorer — heuristic scoring, judge parsing, and helpers."""

import json

import pytest

from src.config import ExecutionConfig, ResearchConfig, ScoringConfig
from src.scorer import (
    GAP_KINDS,
    HeuristicBreakdown,
    IterationScore,
    _extract_section,
    _fuzzy_match,
    combine_scores,
    heuristic_breakdown,
    heuristic_score,
    parse_gaps_identified,
    parse_judge_response,
    quality_score_from_judge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_config() -> ResearchConfig:
    return ResearchConfig(
        topic="Compare API gateways",
        goal="Comparison report",
        dimensions=("REST vs HTTP API", "WebSocket API", "Authentication"),
        scoring=ScoringConfig(
            min_dimensions_per_iteration=1,
            target_dimensions_total=3,
            evidence_types=(
                "comparison_table",
                "pricing_data",
                "code_example",
                "trade_off_analysis",
            ),
        ),
    )


RICH_FINDINGS = """\
### Findings

REST API costs $3.50 per million requests while HTTP API costs $1.00,
representing a 71% cost reduction. As of 2026-04-15, the v2.4.0 release
adds private endpoint support. See [source: aws.amazon.com/api-gateway](https://aws.amazon.com/api-gateway/)
and [Issue #1234](https://github.com/aws/aws-cdk/issues/1234) for context.

| Feature | REST API | HTTP API |
|---------|----------|----------|
| Caching | Yes      | No       |
| WAF     | Yes      | No       |

```python
import boto3
client = boto3.client('apigateway')
```

However, the trade-off is that REST API is more expensive.

The architecture of the system involves a flow from client to gateway.

Latency benchmarks: REST API averages 35ms, HTTP API averages 12ms.
Memory footprint: REST API ~512MB, HTTP API ~128MB. See more at
https://aws.amazon.com/blogs/api-gateway-perf and the official docs.

### New Questions

- How does AppSync compare?
- What are WebSocket limits?
- VPC link latency?
"""

MINIMAL_FINDINGS = "Some brief text about APIs."


# ---------------------------------------------------------------------------
# IterationScore
# ---------------------------------------------------------------------------

class TestIterationScore:
    def test_defaults(self):
        s = IterationScore()
        assert s.coverage == 0.0
        assert s.quality == 0.0
        assert s.total == 0.0
        assert s.dimensions_covered == []
        assert s.gaps == []

    def test_has_no_status_property(self):
        """Status property was removed — keep/discard is decided by orchestrator."""
        s = IterationScore(total=50.0)
        assert not hasattr(s, "status")


# ---------------------------------------------------------------------------
# _fuzzy_match
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    def test_match_found(self):
        assert _fuzzy_match("REST vs HTTP API", "The REST API and HTTP API differ")

    def test_no_match(self):
        assert not _fuzzy_match("WebSocket API", "nothing relevant here")

    def test_short_words_ignored(self):
        # Words <= 3 chars are filtered out
        assert not _fuzzy_match("a b c d", "a b c d in the text")

    def test_case_insensitive(self):
        assert _fuzzy_match("Authentication Options", "the authentication options are varied")

    def test_empty_dimension(self):
        assert not _fuzzy_match("", "some text")

    def test_partial_keyword_match(self):
        # Needs at least half of keywords
        assert _fuzzy_match(
            "REST API pricing performance differences",
            "REST API has different pricing tiers",
        )


# ---------------------------------------------------------------------------
# _extract_section
# ---------------------------------------------------------------------------

class TestExtractSection:
    def test_extracts_section(self):
        text = "# Intro\nfoo\n## New Questions\n- Q1\n- Q2\n## Next\nbar"
        result = _extract_section(text, "New Questions")
        assert "Q1" in result
        assert "Q2" in result
        assert "bar" not in result

    def test_missing_section(self):
        assert _extract_section("# Only this heading\ncontent", "Missing") == ""

    def test_section_at_end(self):
        text = "# Intro\nfoo\n## New Questions\n- Q1\n- Q2"
        result = _extract_section(text, "New Questions")
        assert "Q1" in result

    def test_case_insensitive(self):
        text = "## new questions\n- item"
        result = _extract_section(text, "New Questions")
        assert "item" in result


# ---------------------------------------------------------------------------
# heuristic_score
# ---------------------------------------------------------------------------

class TestHeuristicScore:
    def test_rich_findings_scores_high(self, sample_config):
        score = heuristic_score(RICH_FINDINGS, sample_config, [])
        assert score >= 70.0  # has table, pricing, code, trade-off, questions

    def test_minimal_findings_scores_low(self, sample_config):
        score = heuristic_score(MINIMAL_FINDINGS, sample_config, [])
        assert score < 30.0

    def test_empty_findings(self, sample_config):
        score = heuristic_score("", sample_config, [])
        assert score == 0.0

    def test_no_dimensions_configured(self):
        cfg = ResearchConfig(topic="t", goal="g", dimensions=())
        score = heuristic_score(RICH_FINDINGS, cfg, [])
        # Should still get points for evidence, questions, length
        assert score > 0.0

    def test_score_range(self, sample_config):
        score = heuristic_score(RICH_FINDINGS, sample_config, [])
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# heuristic_breakdown — per-component decomposition
# ---------------------------------------------------------------------------

class TestHeuristicBreakdown:
    """Cover the breakdown structure and the scorer plan Phase 1 changes:
    target-dimension coverage and the logarithmic length curve."""

    def test_breakdown_total_matches_heuristic_score(self, sample_config):
        """The wrapper should be a thin pass-through to .total."""
        bd = heuristic_breakdown(RICH_FINDINGS, sample_config, [])
        assert bd.total == heuristic_score(RICH_FINDINGS, sample_config, [])

    def test_breakdown_components_are_populated(self, sample_config):
        bd = heuristic_breakdown(RICH_FINDINGS, sample_config, [])
        assert bd.dimension_points > 0
        assert bd.evidence_points > 0
        assert bd.new_questions_points > 0
        assert bd.length_points > 0

    def test_empty_findings_produce_empty_breakdown(self, sample_config):
        bd = heuristic_breakdown("", sample_config, [])
        assert bd.total == 0.0
        assert bd.dimension_points == 0.0
        assert bd.evidence_points == 0.0
        assert bd.new_questions_points == 0.0
        assert bd.length_points == 0.0

    def test_target_dimension_mode_marks_target(self, sample_config):
        bd = heuristic_breakdown(
            RICH_FINDINGS, sample_config, [], target_dimension="REST vs HTTP API"
        )
        assert bd.target_dimension == "REST vs HTTP API"

    def test_target_dimension_rewards_focus(self, sample_config):
        """A finding that focuses on the target dimension scores higher
        on the dimension axis than one that scatters across multiple
        configured dimensions."""
        focused = (
            "REST vs HTTP API: REST API differs from HTTP API in caching, "
            "WAF support, and pricing tiers. The REST API has caching; the "
            "HTTP API does not. Both expose 4566. Pricing for REST API is "
            "$3.50 per million requests, HTTP API is $1.00 per million. "
            "However, the trade-off is REST is more expensive."
        )
        scattered = (
            "WebSocket API and Authentication and REST vs HTTP API are all "
            "different things. WebSocket API is for streams. Authentication "
            "covers IAM. REST and HTTP differ on caching."
        )
        focused_bd = heuristic_breakdown(
            focused, sample_config, [], target_dimension="REST vs HTTP API"
        )
        scattered_bd = heuristic_breakdown(
            scattered, sample_config, [], target_dimension="REST vs HTTP API"
        )
        assert focused_bd.dimension_points > scattered_bd.dimension_points

    def test_target_dimension_mode_full_credit_when_only_target_mentioned(self, sample_config):
        """If the findings mention ONLY the target dimension, target_focus
        points should land at the full _TARGET_FOCUS_POINTS = 25 (70% on
        target + 30% drift bonus)."""
        text = (
            "REST API differs from HTTP API in caching, WAF support, and "
            "pricing tiers. The REST API has caching; the HTTP API does not."
        )
        bd = heuristic_breakdown(
            text, sample_config, [], target_dimension="REST vs HTTP API"
        )
        # 70% target hit + 30% no-drift = 25.0 (the new universal-signal max)
        assert bd.target_focus_points == 25.0
        # Backward-compat alias still readable.
        assert bd.dimension_points == 25.0

    def test_target_dimension_mode_penalises_drift(self, sample_config):
        """A finding that mentions every other dimension instead of the
        target should score very low on the dimension axis."""
        text = (
            "WebSocket API is great for streaming. Authentication options "
            "include IAM, Cognito, and Lambda authorizers."
        )
        bd = heuristic_breakdown(
            text, sample_config, [], target_dimension="REST vs HTTP API"
        )
        # No on-target hit + full drift = 0.0
        assert bd.dimension_points == 0.0

    def test_legacy_mode_when_target_dimension_is_none(self, sample_config):
        """Without target_dimension, legacy 'count of dimensions
        mentioned' scoring kicks in."""
        bd_legacy = heuristic_breakdown(RICH_FINDINGS, sample_config, [])
        bd_target = heuristic_breakdown(
            RICH_FINDINGS, sample_config, [], target_dimension="REST vs HTTP API"
        )
        # Both modes are valid; the values just differ by scoring strategy.
        # Sanity-check both are within range.
        assert 0.0 <= bd_legacy.dimension_points <= 40.0
        assert 0.0 <= bd_target.dimension_points <= 40.0


class TestUniversalSignalCitations:
    """Citations are dimension-agnostic: any well-evidenced finding has
    URLs, source markers, and issue references regardless of topic."""

    def test_zero_citations_zero_points(self, sample_config):
        bd = heuristic_breakdown("plain prose with no urls or sources", sample_config, [])
        assert bd.citations_points == 0.0

    def test_url_counts_as_citation(self, sample_config):
        text = "See https://example.com/docs for details."
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.citations_points > 0.0

    def test_source_marker_counts(self, sample_config):
        text = "Per [source: docs.example.com](https://example.com), the price is $5."
        bd = heuristic_breakdown(text, sample_config, [])
        # Both [source:..] and [text](url) and the inner URL match.
        assert bd.citations_points > 0.0

    def test_issue_reference_counts(self, sample_config):
        text = "Bug confirmed in [Issue #470](https://github.com/x/y/issues/470)."
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.citations_points > 0.0

    def test_citations_saturate(self, sample_config):
        text = " ".join(f"https://example.com/{i}" for i in range(50))
        bd = heuristic_breakdown(text, sample_config, [])
        # Saturates at _CITATIONS_POINTS = 25.0
        assert bd.citations_points <= 25.0
        assert bd.citations_points >= 24.0  # near the cap with 50 URLs


class TestUniversalSignalConcreteData:
    """Concrete data is dimension-agnostic: prices, percentages, sizes,
    durations, versions, and dates are all verifiable across any topic."""

    def test_zero_concrete_data_zero_points(self, sample_config):
        bd = heuristic_breakdown("vague prose about things", sample_config, [])
        assert bd.concrete_data_points == 0.0

    def test_price_counts(self, sample_config):
        bd = heuristic_breakdown("Costs $39/month", sample_config, [])
        assert bd.concrete_data_points > 0.0

    def test_percentage_counts(self, sample_config):
        bd = heuristic_breakdown("CPU usage drops by 35% under load", sample_config, [])
        assert bd.concrete_data_points > 0.0

    def test_size_unit_counts(self, sample_config):
        bd = heuristic_breakdown("Image size: 270 MB; idle RAM: 21 MB", sample_config, [])
        assert bd.concrete_data_points > 0.0

    def test_duration_counts(self, sample_config):
        bd = heuristic_breakdown("Startup time: 24 ms (vs 15 sec for LocalStack)", sample_config, [])
        assert bd.concrete_data_points > 0.0

    def test_version_tag_counts(self, sample_config):
        bd = heuristic_breakdown("Released v1.4.0 last week, fix in v1.5.2", sample_config, [])
        assert bd.concrete_data_points > 0.0

    def test_iso_date_counts(self, sample_config):
        bd = heuristic_breakdown("On 2026-03-23 the repo was archived", sample_config, [])
        assert bd.concrete_data_points > 0.0


class TestUniversalSignalStructure:
    """Structure is dimension-agnostic: tables, code blocks, nested
    headings, and bullet lists distinguish well-organised findings from
    unstructured prose."""

    def test_zero_structure_zero_points(self, sample_config):
        bd = heuristic_breakdown("just one paragraph of plain prose.", sample_config, [])
        assert bd.structure_points == 0.0

    def test_table_contributes(self, sample_config):
        text = "| Col A | Col B |\n|---|---|\n| x | y |\n"
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.structure_points > 0.0

    def test_code_block_contributes(self, sample_config):
        text = "```\nimport boto3\n```\n"
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.structure_points > 0.0

    def test_nested_heading_contributes(self, sample_config):
        text = "## Section\n\n### Subsection content here.\n"
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.structure_points > 0.0

    def test_bullets_contribute(self, sample_config):
        text = "- item one\n- item two\n- item three\n"
        bd = heuristic_breakdown(text, sample_config, [])
        assert bd.structure_points > 0.0


class TestParseGapsIdentified:
    """Discovery plan Phase 1 #1: gap shape upgrade with backward
    compatibility for the legacy bare-string form."""

    def test_empty_input(self):
        assert parse_gaps_identified([]) == []
        assert parse_gaps_identified(None) == []  # type: ignore[arg-type]

    def test_legacy_bare_string_normalises(self):
        result = parse_gaps_identified(["Some gap topic that is long enough"])
        assert len(result) == 1
        item = result[0]
        assert item["topic"] == "Some gap topic that is long enough"
        assert item["kind"] == "research_target"
        assert item["investigatable"] is True
        assert item["confidence"] == 5
        assert item["_source_shape"] == "bare_string"

    def test_structured_form_passes_through(self):
        gap = {
            "topic": "Migration cost benchmarks for X under Y conditions",
            "why_it_matters": "Operators need this to budget the migration timeline",
            "kind": "refinement",
            "investigatable": True,
            "confidence": 8,
        }
        result = parse_gaps_identified([gap])
        assert len(result) == 1
        item = result[0]
        assert item["topic"] == gap["topic"]
        assert item["kind"] == "refinement"
        assert item["confidence"] == 8
        assert item["_source_shape"] == "structured"

    def test_invalid_kind_falls_back_to_research_target(self):
        gap = {
            "topic": "A reasonably long topic for a gap",
            "why_it_matters": "Reason",
            "kind": "garbage_value",
            "investigatable": True,
            "confidence": 5,
        }
        result = parse_gaps_identified([gap])
        assert result[0]["kind"] == "research_target"

    def test_confidence_clamped_to_1_10(self):
        gap_low = {"topic": "topic 1", "why_it_matters": "x", "kind": "research_target",
                   "investigatable": True, "confidence": -3}
        gap_high = {"topic": "topic 2", "why_it_matters": "x", "kind": "research_target",
                    "investigatable": True, "confidence": 99}
        gap_garbage = {"topic": "topic 3", "why_it_matters": "x", "kind": "research_target",
                       "investigatable": True, "confidence": "lots"}
        result = parse_gaps_identified([gap_low, gap_high, gap_garbage])
        assert result[0]["confidence"] == 1
        assert result[1]["confidence"] == 10
        assert result[2]["confidence"] == 5  # default fallback

    def test_empty_topic_skipped(self):
        result = parse_gaps_identified([
            {"topic": "", "why_it_matters": "x", "kind": "research_target",
             "investigatable": True, "confidence": 5},
            "",
            "   ",
        ])
        assert result == []

    def test_kinds_constant_lists_three_values(self):
        # Sanity check the public constant exposes the documented kinds.
        assert set(GAP_KINDS) == {"research_target", "refinement", "critique"}

    def test_mixed_input(self):
        result = parse_gaps_identified([
            "bare string gap topic that is long enough",
            {"topic": "structured gap topic that is also long",
             "why_it_matters": "matters", "kind": "critique",
             "investigatable": False, "confidence": 7},
            42,  # invalid type — silently skipped
        ])
        assert len(result) == 2
        assert result[0]["_source_shape"] == "bare_string"
        assert result[1]["_source_shape"] == "structured"


class TestLengthCurve:
    """Verify the logarithmic length component (scorer plan Phase 1, #6)."""

    def _length_only(self, words: int, sample_config) -> float:
        text = " ".join(["foo"] * words) if words > 0 else ""
        return heuristic_breakdown(text, sample_config, []).length_points

    def test_zero_words_zero_points(self, sample_config):
        assert self._length_only(0, sample_config) == 0.0

    def test_target_word_count_near_cap(self, sample_config):
        # 500 words should land at or just under the cap.
        pts = self._length_only(500, sample_config)
        assert 9.0 <= pts <= 10.0

    def test_long_findings_capped(self, sample_config):
        # Padding past the target should not earn extra credit.
        pts_500 = self._length_only(500, sample_config)
        pts_5000 = self._length_only(5000, sample_config)
        assert pts_5000 <= 10.0
        assert pts_5000 == pytest.approx(pts_500, abs=1.5)

    def test_short_findings_get_substantial_credit(self, sample_config):
        # Log curve gives short-but-substantive findings a meaningful
        # share of the points (linear curve gave 100 words just 2.0).
        pts = self._length_only(100, sample_config)
        assert pts > 5.0


class TestIterationScoreBreakdownFields:
    """Phase 1 (#3): IterationScore now carries component breakdowns and
    per-axis judge scores so the run.log + dashboard can surface them."""

    def test_default_iteration_score_has_breakdown(self):
        score = IterationScore()
        assert isinstance(score.heuristic_breakdown, HeuristicBreakdown)
        assert score.heuristic_breakdown.total == 0.0

    def test_default_iteration_score_has_judge_axes(self):
        score = IterationScore()
        assert score.judge_depth == 0
        assert score.judge_accuracy == 0
        assert score.judge_novelty == 0
        assert score.judge_actionability == 0

    def test_iteration_score_can_carry_populated_breakdown(self):
        bd = HeuristicBreakdown(
            target_focus_points=20.0,
            citations_points=18.0,
            concrete_data_points=15.0,
            structure_points=10.0,
            length_points=8.0,
            total=71.0,
            target_dimension="X",
        )
        score = IterationScore(
            coverage=71.0,
            quality=65.0,
            total=67.4,
            heuristic_breakdown=bd,
            judge_depth=8,
            judge_accuracy=7,
            judge_novelty=6,
            judge_actionability=7,
        )
        assert score.heuristic_breakdown.target_dimension == "X"
        assert score.judge_novelty == 6
        # Backward-compat property aliases:
        assert score.heuristic_breakdown.dimension_points == 20.0
        assert score.heuristic_breakdown.evidence_points == 15.0
        assert score.heuristic_breakdown.new_questions_points == 10.0


# ---------------------------------------------------------------------------
# parse_judge_response
# ---------------------------------------------------------------------------

class TestParseJudgeResponse:
    def test_plain_json(self):
        raw = '{"depth": 7, "accuracy": 8, "novelty": 6, "actionability": 7, "dimensions_covered": ["REST"], "gaps_identified": ["WebSocket"], "reasoning": "good"}'
        result = parse_judge_response(raw)
        assert result["depth"] == 7
        assert result["accuracy"] == 8
        assert result["dimensions_covered"] == ["REST"]

    def test_fenced_json(self):
        raw = 'Here is my evaluation:\n```json\n{"depth": 5, "accuracy": 5, "novelty": 5, "actionability": 5, "dimensions_covered": [], "gaps_identified": [], "reasoning": "ok"}\n```'
        result = parse_judge_response(raw)
        assert result["depth"] == 5

    def test_json_with_surrounding_text(self):
        raw = 'My analysis: {"depth": 9, "accuracy": 8, "novelty": 7, "actionability": 8, "dimensions_covered": ["A"], "gaps_identified": ["B"], "reasoning": "great"} That is all.'
        result = parse_judge_response(raw)
        assert result["depth"] == 9

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_judge_response("not json at all")

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            parse_judge_response("")


# ---------------------------------------------------------------------------
# quality_score_from_judge
# ---------------------------------------------------------------------------

class TestQualityScoreFromJudge:
    def test_perfect_scores(self):
        judge = {"depth": 10, "accuracy": 10, "novelty": 10, "actionability": 10}
        assert quality_score_from_judge(judge) == 100.0

    def test_minimum_scores(self):
        judge = {"depth": 1, "accuracy": 1, "novelty": 1, "actionability": 1}
        assert quality_score_from_judge(judge) == 10.0

    def test_average_scores(self):
        judge = {"depth": 5, "accuracy": 5, "novelty": 5, "actionability": 5}
        assert quality_score_from_judge(judge) == 50.0

    def test_missing_axes_default_to_5(self):
        judge = {"depth": 10}  # others default to 5
        score = quality_score_from_judge(judge)
        assert score == 62.5  # (10+5+5+5) / 40 * 100

    def test_mixed_scores(self):
        judge = {"depth": 8, "accuracy": 7, "novelty": 9, "actionability": 6}
        expected = round((8 + 7 + 9 + 6) / 40 * 100, 1)
        assert quality_score_from_judge(judge) == expected


# ---------------------------------------------------------------------------
# combine_scores
# ---------------------------------------------------------------------------

class TestCombineScores:
    def test_weights(self):
        assert combine_scores(100.0, 100.0) == 100.0
        assert combine_scores(0.0, 0.0) == 0.0

    def test_coverage_weight_40(self):
        assert combine_scores(100.0, 0.0) == 40.0

    def test_quality_weight_60(self):
        assert combine_scores(0.0, 100.0) == 60.0

    def test_mixed(self):
        result = combine_scores(80.0, 70.0)
        expected = round(0.4 * 80.0 + 0.6 * 70.0, 1)
        assert result == expected
