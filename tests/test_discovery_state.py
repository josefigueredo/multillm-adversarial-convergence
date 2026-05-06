"""Tests for Discovery plan Phase 2: persistent gap state schema.

Covers:
- ``GapEntry`` dataclass + ``record_gap()`` semantics
- Sidecar I/O round-trip (``write_discovered_gaps_sidecar`` /
  ``read_discovered_gaps_sidecar``)
- ``resume_state()`` from sidecar (preferred) vs from
  ``results.tsv`` legacy column (fallback)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.run_io import (
    DISCOVERED_GAPS_SIDECAR,
    RESULTS_FIELDS,
    read_discovered_gaps_sidecar,
    write_discovered_gaps_sidecar,
)
from src.run_state import (
    GapEntry,
    deserialise_discovered_gaps,
    record_gap,
    resume_state,
    serialise_discovered_gaps,
)


# ---------------------------------------------------------------------------
# GapEntry + record_gap
# ---------------------------------------------------------------------------

class TestRecordGapNew:
    def test_creates_new_entry_returns_is_new_true(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        entry, is_new = record_gap(
            discovered_gaps=gaps,
            discovered_dimensions=topics,
            canonical_topic="container startup latency",
            display_topic="Container startup latency",
            iteration=2,
            judge_name="gemini-cli",
            kind="research_target",
            confidence=7,
        )
        assert is_new is True
        assert entry.canonical_topic == "container startup latency"
        assert entry.display_topic == "Container startup latency"
        assert entry.first_seen_iter == 2
        assert entry.occurrences == 1
        assert entry.iterations_seen == [2]
        assert entry.judges_seen == ["gemini-cli"]
        assert entry.kind == "research_target"
        assert entry.confidences == [7]
        assert entry.promoted is True

    def test_updates_legacy_dimensions_list(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps,
            discovered_dimensions=topics,
            canonical_topic="x",
            display_topic="X dimension",
            iteration=1,
        )
        assert "X dimension" in topics

    def test_no_judge_name_yields_empty_judges_list(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        entry, _ = record_gap(
            discovered_gaps=gaps,
            discovered_dimensions=topics,
            canonical_topic="x",
            display_topic="X",
            iteration=1,
        )
        assert entry.judges_seen == []


class TestRecordGapUpdate:
    def test_existing_entry_increments_occurrences(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps,
            discovered_dimensions=topics,
            canonical_topic="x",
            display_topic="X",
            iteration=1,
            judge_name="claude-cli",
            confidence=5,
        )
        entry, is_new = record_gap(
            discovered_gaps=gaps,
            discovered_dimensions=topics,
            canonical_topic="x",
            display_topic="X — refined wording",
            iteration=3,
            judge_name="codex-cli",
            confidence=8,
        )
        assert is_new is False
        assert entry.occurrences == 2
        assert entry.iterations_seen == [1, 3]
        assert entry.judges_seen == ["claude-cli", "codex-cli"]
        assert entry.confidences == [5, 8]
        # Most-recent display form wins
        assert entry.display_topic == "X — refined wording"

    def test_iteration_dedupe_in_iterations_seen(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X", iteration=2)
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X", iteration=2)
        entry = gaps["x"]
        # Same iteration twice — counted in occurrences but not double-listed
        assert entry.occurrences == 2
        assert entry.iterations_seen == [2]

    def test_judge_dedupe_in_judges_seen(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X",
                   iteration=1, judge_name="gemini-cli")
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X",
                   iteration=2, judge_name="gemini-cli")
        assert gaps["x"].judges_seen == ["gemini-cli"]

    def test_legacy_dimensions_not_double_appended(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = ["X"]  # already there
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X", iteration=1)
        record_gap(discovered_gaps=gaps, discovered_dimensions=topics,
                   canonical_topic="x", display_topic="X", iteration=2)
        assert topics.count("X") == 1


# ---------------------------------------------------------------------------
# Serialise / Deserialise
# ---------------------------------------------------------------------------

class TestSerialise:
    def test_roundtrip(self):
        original = {
            "topic 1": GapEntry(
                canonical_topic="topic 1",
                display_topic="Topic 1",
                first_seen_iter=2,
                occurrences=3,
                iterations_seen=[2, 3, 4],
                judges_seen=["a", "b"],
                kind="refinement",
                confidences=[6, 7, 8],
                promoted=True,
            ),
        }
        payload = serialise_discovered_gaps(original)
        # Plain JSON-able dict
        json.dumps(payload)
        recovered = deserialise_discovered_gaps(payload)
        assert recovered == original

    def test_deserialise_tolerates_missing_fields(self):
        # Old / partial sidecar that's missing some fields
        payload = {
            "topic 1": {"canonical_topic": "topic 1", "display_topic": "Topic 1",
                        "first_seen_iter": 1},
        }
        result = deserialise_discovered_gaps(payload)
        assert "topic 1" in result
        entry = result["topic 1"]
        assert entry.first_seen_iter == 1
        assert entry.occurrences == 1  # default
        assert entry.kind == "research_target"  # default
        assert entry.promoted is True  # default

    def test_deserialise_skips_malformed_entries(self):
        payload = {
            "good": {"canonical_topic": "good", "display_topic": "Good",
                     "first_seen_iter": 1},
            "bad": "not a dict",  # malformed
        }
        # Bad entries become None on entry construction but our impl
        # tolerates missing fields, not non-dict types — so this asserts
        # the function doesn't crash, and returns at least the good one.
        result = deserialise_discovered_gaps(payload)  # type: ignore[arg-type]
        assert "good" in result


# ---------------------------------------------------------------------------
# Sidecar I/O
# ---------------------------------------------------------------------------

class TestSidecarIO:
    def test_write_creates_file(self, tmp_path: Path):
        gaps = {
            "x": GapEntry(canonical_topic="x", display_topic="X", first_seen_iter=1),
        }
        path = write_discovered_gaps_sidecar(tmp_path, gaps)
        assert path.exists()
        assert path.name == DISCOVERED_GAPS_SIDECAR
        # Content is valid JSON
        json.loads(path.read_text(encoding="utf-8"))

    def test_read_returns_empty_when_missing(self, tmp_path: Path):
        result = read_discovered_gaps_sidecar(tmp_path)
        assert result == {}

    def test_read_tolerates_malformed_json(self, tmp_path: Path):
        (tmp_path / DISCOVERED_GAPS_SIDECAR).write_text("not json {{{", encoding="utf-8")
        result = read_discovered_gaps_sidecar(tmp_path)
        assert result == {}

    def test_read_tolerates_non_dict_payload(self, tmp_path: Path):
        (tmp_path / DISCOVERED_GAPS_SIDECAR).write_text('["a","b"]', encoding="utf-8")
        result = read_discovered_gaps_sidecar(tmp_path)
        assert result == {}

    def test_roundtrip(self, tmp_path: Path):
        gaps = {
            "x": GapEntry(
                canonical_topic="x", display_topic="X — display",
                first_seen_iter=2, occurrences=4, iterations_seen=[2, 3, 4, 5],
                judges_seen=["gemini", "codex"], kind="refinement",
                confidences=[6, 7, 8, 9], promoted=True,
            ),
        }
        write_discovered_gaps_sidecar(tmp_path, gaps)
        recovered = read_discovered_gaps_sidecar(tmp_path)
        assert recovered == gaps


# ---------------------------------------------------------------------------
# Resume state
# ---------------------------------------------------------------------------

def _seed_iteration_files(iterations_dir: Path, count: int) -> None:
    iterations_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        (iterations_dir / f"iter_{i:03d}.md").write_text(f"# Iteration {i}\n", encoding="utf-8")


def _write_results_tsv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            full = {field: row.get(field, "") for field in RESULTS_FIELDS}
            writer.writerow(full)


class TestResumeFromSidecar:
    def test_sidecar_loaded_when_present(self, tmp_path: Path):
        iterations_dir = tmp_path / "iterations"
        results_path = tmp_path / "results.tsv"
        kb_path = tmp_path / "knowledge_base.md"
        sidecar = tmp_path / "discovered_gaps.json"

        _seed_iteration_files(iterations_dir, count=2)
        _write_results_tsv(results_path, [
            {"iteration": "001", "dimension": "Pricing", "status": "keep",
             "total_score": "75", "discovered_gaps": '["LegacyOnlyTopic"]'},
        ])
        # Pre-populate sidecar with a different topic so we can tell which
        # source actually got loaded.
        gaps = {
            "structured topic": GapEntry(
                canonical_topic="structured topic",
                display_topic="Structured topic",
                first_seen_iter=1,
                occurrences=2,
                iterations_seen=[1, 2],
                kind="refinement",
            ),
        }
        write_discovered_gaps_sidecar(tmp_path, gaps)

        state = resume_state(
            iterations_dir=iterations_dir,
            results_path=results_path,
            knowledge_base_path=kb_path,
            configured_dimensions=("Pricing",),
            max_attempts_per_dimension=3,
            discovered_gaps_sidecar=sidecar,
        )
        # Sidecar wins — discovered_gaps is from the sidecar, not legacy
        assert "structured topic" in state["discovered_gaps"]
        assert state["discovered_gaps"]["structured topic"].kind == "refinement"
        # Legacy column was NOT used to synthesise extra entries
        assert "LegacyOnlyTopic" not in state["discovered_dimensions"]


class TestResumeFromLegacyTsv:
    def test_legacy_fallback_synthesises_gap_entries(self, tmp_path: Path):
        iterations_dir = tmp_path / "iterations"
        results_path = tmp_path / "results.tsv"
        kb_path = tmp_path / "knowledge_base.md"
        # No sidecar file present.

        _seed_iteration_files(iterations_dir, count=1)
        _write_results_tsv(results_path, [
            {"iteration": "001", "dimension": "Pricing", "status": "keep",
             "total_score": "75",
             "discovered_gaps": '["Migration runbook coverage", "Latency benchmark variance"]'},
        ])

        state = resume_state(
            iterations_dir=iterations_dir,
            results_path=results_path,
            knowledge_base_path=kb_path,
            configured_dimensions=("Pricing",),
            max_attempts_per_dimension=3,
            discovered_gaps_sidecar=tmp_path / "discovered_gaps.json",  # absent
        )
        # Legacy column is parsed and GapEntry records synthesised
        assert "Migration runbook coverage" in state["discovered_dimensions"]
        assert "Latency benchmark variance" in state["discovered_dimensions"]
        assert len(state["discovered_gaps"]) == 2
        # Synthesised entries get conservative defaults
        for entry in state["discovered_gaps"].values():
            assert entry.kind == "research_target"
            assert entry.confidences == [5]
            assert entry.first_seen_iter == 1
            assert entry.promoted is True

    def test_legacy_fallback_does_not_re_add_when_already_discovered(self, tmp_path: Path):
        """Same canonical topic emitted across multiple rows is added
        once (set-style behavior in the legacy parser)."""
        iterations_dir = tmp_path / "iterations"
        results_path = tmp_path / "results.tsv"
        kb_path = tmp_path / "knowledge_base.md"

        _seed_iteration_files(iterations_dir, count=2)
        _write_results_tsv(results_path, [
            {"iteration": "001", "dimension": "Pricing", "status": "keep",
             "total_score": "75",
             "discovered_gaps": '["Latency benchmark variance"]'},
            {"iteration": "002", "dimension": "Caching strategy", "status": "keep",
             "total_score": "70",
             "discovered_gaps": '["Latency benchmark variance"]'},  # re-emit
        ])

        state = resume_state(
            iterations_dir=iterations_dir,
            results_path=results_path,
            knowledge_base_path=kb_path,
            configured_dimensions=("Pricing",),
            max_attempts_per_dimension=3,
        )
        # Topic appears once, not twice
        assert state["discovered_dimensions"].count("Latency benchmark variance") == 1
        # And exactly one synthesised entry under canonical key
        assert len(state["discovered_gaps"]) == 1


class TestPromotionLogic:
    """Discovery plan Phase 3: cross-iteration clustering with
    re-discovery promotion + confidence tiering."""

    def test_disabled_auto_promotes_everything(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=3,
            promotion_enabled=False,
        )
        assert gaps["x"].promoted is True
        assert "X" in topics

    def test_enabled_single_low_confidence_not_promoted(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=4,
            promotion_enabled=True,
        )
        # 1 occurrence + low confidence + research_target → not promoted
        assert gaps["x"].promoted is False
        assert "X" not in topics  # absent from hypothesis pool view

    def test_enabled_single_high_confidence_promoted(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=9,
            promotion_enabled=True,
        )
        # Single occurrence with mean(confidences) >= 8 → promoted
        assert gaps["x"].promoted is True
        assert "X" in topics

    def test_enabled_repeated_occurrence_promotes(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=3,
            promotion_enabled=True,
        )
        assert gaps["x"].promoted is False
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=2, confidence=3,
            promotion_enabled=True,
        )
        # 2 occurrences → promoted regardless of confidence
        assert gaps["x"].promoted is True
        assert "X" in topics

    def test_enabled_refinement_kind_promotes_immediately(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=4, kind="refinement",
            promotion_enabled=True,
        )
        # Refinements target an existing dim and don't need cross-iter
        # confirmation — promoted on single sighting even at low conf
        assert gaps["x"].promoted is True

    def test_promotion_is_sticky_once_earned(self):
        gaps: dict[str, GapEntry] = {}
        topics: list[str] = []
        # First sighting — single high-conf — promoted
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=1, confidence=9,
            promotion_enabled=True,
        )
        assert gaps["x"].promoted is True
        # Second sighting — low conf — should NOT demote
        record_gap(
            discovered_gaps=gaps, discovered_dimensions=topics,
            canonical_topic="x", display_topic="X",
            iteration=2, confidence=2,
            promotion_enabled=True,
        )
        assert gaps["x"].promoted is True


class TestResumeNoIterations:
    def test_empty_run_returns_blank_state(self, tmp_path: Path):
        state = resume_state(
            iterations_dir=tmp_path / "iterations",
            results_path=tmp_path / "results.tsv",
            knowledge_base_path=tmp_path / "kb.md",
            configured_dimensions=(),
            max_attempts_per_dimension=3,
        )
        assert state["iteration"] == 0
        assert state["discovered_gaps"] == {}
        assert state["discovered_dimensions"] == []
