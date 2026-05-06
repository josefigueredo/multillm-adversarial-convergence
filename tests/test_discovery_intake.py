"""Tests for the gap intake processing pipeline.

Discovery plan Phase 1 #2: ``process_discovered_gaps()`` in
``src.research_loop`` filters judge-emitted gaps before they enter
``state.discovered_dimensions``. Each rejection emits an
``audit_trail`` event with a typed reason so operators can inspect
what was thrown out.
"""

from __future__ import annotations

import pytest

from src.config import DiscoveryConfig, ResearchConfig
from src.research_loop import (
    LoopState,
    _canonical_topic,
    _looks_spanish,
    process_discovered_gaps,
)


class _RecordingAudit:
    """Drop-in stand-in for the audit_trail object that records every
    ``emit`` call so tests can assert on them.

    Mirrors AuditTrailWriter's signature: ``emit(event: str, **fields)``.
    Tests assert on ``self.events`` as ``[(event_name, fields_dict), ...]``.
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def emit(self, event_type: str, **fields) -> None:
        self.events.append((event_type, fields))


def _gap(topic: str, **overrides) -> dict:
    """Build a structured gap record with sensible defaults."""
    base = {
        "topic": topic,
        "why_it_matters": "Operators care about this for their migration",
        "kind": "research_target",
        "investigatable": True,
        "confidence": 7,
        "_source_shape": "structured",
    }
    base.update(overrides)
    return base


@pytest.fixture
def config() -> ResearchConfig:
    return ResearchConfig(
        topic="Cloud emulation alternatives",
        goal="Decision report",
        dimensions=("Pricing comparison", "Migration effort", "Service coverage"),
        discovery=DiscoveryConfig(language_filter="en", dedupe_threshold=0.85),
    )


@pytest.fixture
def state() -> LoopState:
    return LoopState(
        iteration=2,
        results=[],
        best_score=0.0,
        best_scores={},
        explored_dimensions=[],
        discovered_dimensions=[],
        dimension_attempts={},
        knowledge_base="",
    )


@pytest.fixture
def audit() -> _RecordingAudit:
    return _RecordingAudit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestCanonicalTopic:
    def test_lowercases_and_collapses_whitespace(self):
        assert _canonical_topic("  Some  Mixed  Case ") == "some mixed case"

    def test_strips_trailing_punctuation(self):
        assert _canonical_topic("A topic.") == "a topic"
        assert _canonical_topic("Question?") == "question"

    def test_idempotent(self):
        once = _canonical_topic("Pricing tier breakdown")
        twice = _canonical_topic(once)
        assert once == twice


class TestLooksSpanish:
    def test_clean_english_returns_false(self):
        assert _looks_spanish("Migration effort from LocalStack to alternatives") is False

    def test_obvious_spanish_returns_true(self):
        # The actual noise pattern observed in the localstack run
        assert _looks_spanish(
            "Verificación de números de tipos de recursos en CloudFormation"
        ) is True
        assert _looks_spanish("Detalle de graceful fallback y hard-fails") is True

    def test_short_text_skipped(self):
        # < 4 tokens — too short to reliably classify
        assert _looks_spanish("de la el") is False

    def test_single_loanword_does_not_trigger(self):
        # A single Spanish loan-word in English text shouldn't trip the filter
        assert _looks_spanish(
            "the localstack alternative is fine but the migration cost is high"
        ) is False


# ---------------------------------------------------------------------------
# process_discovered_gaps
# ---------------------------------------------------------------------------

class TestProcessDiscoveredGaps:
    def test_empty_input(self, config, state, audit):
        result = process_discovered_gaps(
            [], state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert result == []
        assert audit.events == []

    def test_clean_gaps_pass_through(self, config, state, audit):
        gaps = [
            _gap("Container startup latency benchmarks under cold start"),
            _gap("AGPL compatibility analysis for commercial CI/CD use"),
        ]
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert len(result) == 2
        assert audit.events == []

    def test_too_short_filtered(self, config, state, audit):
        gaps = [_gap("short")]  # < 30 chars
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert result == []
        assert len(audit.events) == 1
        assert audit.events[0][0] == "gap_filtered_too_short"

    def test_too_long_filtered(self, config, state, audit):
        gaps = [_gap("x" * 250)]  # > 200 chars
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert result == []
        assert audit.events[0][0] == "gap_filtered_too_long"

    def test_spanish_filtered_with_en_filter(self, config, state, audit):
        gaps = [_gap("Verificación de números de tipos de recursos en CloudFormation")]
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert result == []
        assert audit.events[0][0] == "gap_filtered_non_english"

    def test_spanish_passes_with_filter_disabled(self, state, audit):
        config = ResearchConfig(
            topic="X", goal="Y", dimensions=("D",),
            discovery=DiscoveryConfig(language_filter="none"),
        )
        gaps = [_gap("Verificación de números de tipos de recursos en CloudFormation")]
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="D",
        )
        assert len(result) == 1
        assert audit.events == []

    def test_duplicate_against_configured_dimension_filtered(self, state, audit):
        cfg = ResearchConfig(
            topic="X", goal="Y",
            dimensions=("Pricing comparison across vendors",),
            discovery=DiscoveryConfig(),
        )
        gaps = [_gap("Pricing comparison across vendors and tiers")]  # near-duplicate
        result = process_discovered_gaps(
            gaps, state=state, config=cfg, audit_trail=audit,
            iteration=2, dimension="Pricing comparison across vendors",
        )
        # Levenshtein 0.85 is fairly tight; this exact-prefix near-duplicate
        # should match.  If the threshold were looser the test would still
        # accept duplicates as legitimate.
        assert audit.events[0][0] == "gap_filtered_duplicate"
        assert "matched_topic" in audit.events[0][1]
        assert result == []

    def test_duplicate_against_already_discovered_filtered(self, config, audit):
        state = LoopState(
            iteration=3,
            results=[],
            best_score=0.0,
            best_scores={},
            explored_dimensions=[],
            discovered_dimensions=["Container startup latency benchmark data"],
            dimension_attempts={},
            knowledge_base="",
        )
        gaps = [_gap("Container startup latency benchmark data points")]
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=3, dimension="Pricing comparison",
        )
        assert result == []
        assert audit.events[0][0] == "gap_filtered_duplicate"

    def test_internal_dedupe_within_one_call(self, config, state, audit):
        gaps = [
            _gap("Container startup latency benchmarks under cold start"),
            _gap("Container startup latency benchmarks under cold starts"),  # near-dup
        ]
        result = process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=2, dimension="Pricing comparison",
        )
        assert len(result) == 1
        assert any(e[0] == "gap_filtered_duplicate" for e in audit.events)

    def test_audit_payload_includes_iteration_and_dimension(self, config, state, audit):
        gaps = [_gap("x" * 10)]  # too short
        process_discovered_gaps(
            gaps, state=state, config=config, audit_trail=audit,
            iteration=42, dimension="Migration effort",
        )
        event_type, payload = audit.events[0]
        assert event_type == "gap_filtered_too_short"
        assert payload["iteration"] == 42
        assert payload["dimension"] == "Migration effort"
        assert payload["topic"] == "x" * 10
        assert payload["kind"] == "research_target"
        assert payload["confidence"] == 7
