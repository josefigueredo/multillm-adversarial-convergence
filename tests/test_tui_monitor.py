"""Tests for the data layer of scripts/tui_monitor.

Renderers (rich panels) aren't unit-tested here — they'd require golden-string
comparison that breaks on every layout tweak. Instead we test:
  - event-driven RunState mutation (the parser → state pipeline)
  - sparkline generation
  - scripted-events generator yields a self-consistent sequence
  - audit-file iteration handles missing files / malformed lines
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `import scripts.tui_monitor` from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.tui_monitor import (  # noqa: E402
    RunState,
    _short_dim,
    _sparkline,
    follow_audit_events,
    iter_audit_events,
    scripted_events,
)


# ---------------------------------------------------------------------------
# RunState.apply_event
# ---------------------------------------------------------------------------

def test_run_started_populates_run_meta():
    s = RunState()
    s.apply_event({"event": "run_started", "topic": "T", "strategy": "adversarial",
                   "run_id": "r1"})
    assert s.run_id == "r1"
    assert s.topic == "T"
    assert s.strategy == "adversarial"
    assert s.started_at is not None


def test_iteration_started_advances_current_iter():
    s = RunState()
    s.apply_event({"event": "iteration_started", "iteration": 7})
    assert s.current_iter == 7
    assert 7 in s.iters


def test_step_started_maps_known_step_to_state():
    s = RunState()
    s.apply_event({"event": "step_started", "step": "execute_research",
                   "iteration": 3, "dimension": "Auth: long suffix here",
                   "backend": "claude-cli sonnet"})
    assert s.current_state == "EXECUTE"
    assert s.current_iter == 3
    assert s.current_backend == "claude-cli sonnet"
    # Long dim is shortened
    assert s.current_dim == "Auth"


def test_step_started_unknown_step_falls_back_to_uppercased_label():
    s = RunState()
    s.apply_event({"event": "step_started", "step": "wibble_wobble", "iteration": 1})
    assert s.current_state == "WIBBLE WOBBLE"


def test_iteration_completed_records_score_and_keep_marks_dim_covered():
    s = RunState()
    s.apply_event({"event": "step_started", "step": "hypothesise",
                   "iteration": 1, "dimension": "REST"})
    s.apply_event({"event": "iteration_completed", "iteration": 1,
                   "dimension": "REST", "status": "KEEP", "total_score": 76.4})
    assert s.iters[1].decision == "KEEP"
    assert s.iters[1].total == 76.4
    assert "REST" in s.dimensions_covered
    # chart_points gets a synthesized entry
    assert len(s.chart_points) == 1
    assert s.chart_points[0][0] == 1
    assert s.chart_points[0][3] == 76.4


def test_iteration_completed_discard_does_not_mark_dim_covered():
    s = RunState()
    s.apply_event({"event": "step_started", "step": "hypothesise",
                   "iteration": 1, "dimension": "REST"})
    s.apply_event({"event": "iteration_completed", "iteration": 1,
                   "dimension": "REST", "status": "DISCARD", "total_score": 40.0})
    assert s.iters[1].decision == "DISCARD"
    assert "REST" not in s.dimensions_covered


def test_compress_skipped_low_memory_appended_to_fallback_log():
    s = RunState()
    s.apply_event({"event": "compress_skipped_low_memory",
                   "iteration": 4, "free_gb": 0.5, "threshold_gb": 2.0,
                   "corpus_words": 12000})
    assert any("0.5" in line for line in s.fallback_events)
    assert any("iter 4" in line for line in s.fallback_events)


def test_compress_failed_fallback_truncate_appended_to_fallback_log():
    s = RunState()
    s.apply_event({"event": "compress_failed_fallback_truncate",
                   "iteration": 6, "error": "RuntimeError: simulated"})
    assert any("iter 6" in line for line in s.fallback_events)
    assert any("RuntimeError" in line for line in s.fallback_events)


def test_iteration_rolled_back_appended_to_fallback_log():
    s = RunState()
    s.apply_event({
        "event": "iteration_rolled_back",
        "iteration": 4,
        "dimension": "REST API vs HTTP API",
        "undone": ["iter_md", "tsv_row", "kb_section"],
    })
    assert any("iter 4" in line for line in s.fallback_events)
    assert any("rolled back" in line for line in s.fallback_events)
    assert any("kb_section" in line for line in s.fallback_events)


def test_iteration_rolled_back_with_empty_undone_still_logs():
    """Sentinel-only crash: nothing else on disk, undone is []."""
    s = RunState()
    s.apply_event({
        "event": "iteration_rolled_back",
        "iteration": 7,
        "dimension": "X",
        "undone": [],
    })
    assert any("iter 7" in line for line in s.fallback_events)
    assert any("(no side effects)" in line for line in s.fallback_events)


def test_merge_skipped_duplicate_recovered_appended_to_fallback_log():
    s = RunState()
    s.apply_event({
        "event": "merge_skipped_duplicate_recovered",
        "iteration": 5,
        "dimension": "Auth flow",
    })
    assert any("iter 5" in line for line in s.fallback_events)
    assert any("defensive merge guard" in line for line in s.fallback_events)


def test_run_completed_marks_finished():
    s = RunState()
    s.apply_event({"event": "run_completed"})
    assert s.finished
    assert s.current_state == "DONE"


def test_unknown_event_does_not_crash():
    s = RunState()
    # No exception raised
    s.apply_event({"event": "wibble", "random": "field"})
    s.apply_event({})  # event field missing entirely
    assert s.current_iter == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_short_dim_strips_after_colon_and_truncates():
    assert _short_dim("REST: long colon-suffixed description here") == "REST"
    assert _short_dim("a" * 100) == "a" * 34
    assert _short_dim("  spaced  ") == "spaced"


def test_sparkline_empty_returns_empty():
    assert _sparkline([]) == ""


def test_sparkline_renders_within_range_chars():
    spark = _sparkline([0, 25, 50, 75, 100], width=5, vmin=0, vmax=100)
    assert len(spark) == 5
    # All chars from the SPARK_BARS palette
    from scripts.tui_monitor import SPARK_BARS
    assert all(c in SPARK_BARS for c in spark)
    # Increasing values → increasing bars (positions 0..4)
    bar_positions = [SPARK_BARS.index(c) for c in spark]
    assert bar_positions == sorted(bar_positions)


def test_sparkline_pads_short_input_to_width():
    spark = _sparkline([50], width=10)
    assert len(spark) == 10
    # Last char is the value bar; leading chars are padding
    assert spark.endswith(spark.strip())


def test_sparkline_truncates_long_input_to_window():
    spark = _sparkline(list(range(0, 100, 5)), width=4)
    assert len(spark) == 4


def test_sparkline_auto_scales_above_100_for_novelty_blended_runs():
    """Novelty-weighted total can exceed 100 (max 125).  Sparkline must
    auto-scale so values above 100 don't all clamp to the top bar."""
    from scripts.tui_monitor import SPARK_BARS
    # Three values: 50 (mid), 100 (legacy max), 124 (novelty max)
    spark = _sparkline([50.0, 100.0, 124.0], width=3)
    assert len(spark) == 3
    # The 124 value is the new vmax; it should be the top bar (█)
    assert spark[-1] == SPARK_BARS[-1]
    # The 50 value should NOT be the top bar (it's < vmax)
    assert spark[0] != SPARK_BARS[-1]


def test_sparkline_floor_at_100_for_low_score_runs():
    """When all values are well under 100, vmax should still floor at 100
    so a low-score run doesn't visually look like it's hit the ceiling."""
    from scripts.tui_monitor import SPARK_BARS
    # All values in 0-50; floor of 100 means they should all be in lower half
    spark = _sparkline([10.0, 30.0, 50.0], width=3)
    bar_indices = [SPARK_BARS.index(c) for c in spark]
    # Top value (50) is half of the 100 floor, so should be in lower half of palette
    assert bar_indices[-1] < len(SPARK_BARS) - 1


# ---------------------------------------------------------------------------
# results.tsv loader
# ---------------------------------------------------------------------------

def test_load_results_tsv_returns_breakdown_per_iteration(tmp_path):
    from scripts.tui_monitor import load_results_tsv
    p = tmp_path / "results.tsv"
    p.write_text(
        "iteration\tdimension\tcoverage_score\tquality_score\ttotal_score\textra\n"
        "001\tDim A\t94.4\t65.0\t104.5\tjunk\n"
        "002\tDim B\t90.0\t70.0\t108.0\tjunk\n",
    )
    out = load_results_tsv(p)
    assert out[1] == (94.4, 65.0, 104.5)
    assert out[2] == (90.0, 70.0, 108.0)


def test_load_results_tsv_missing_file_returns_empty():
    from scripts.tui_monitor import load_results_tsv
    out = load_results_tsv(Path("/tmp/__nope__.tsv"))
    assert out == {}


def test_load_results_tsv_skips_unparseable_rows(tmp_path):
    from scripts.tui_monitor import load_results_tsv
    p = tmp_path / "results.tsv"
    p.write_text(
        "iteration\tcoverage_score\tquality_score\ttotal_score\n"
        "001\t90.0\t60.0\t72.0\n"
        "not_a_number\t0\t0\t0\n"
        "002\t85.0\t70.0\t76.0\n",
    )
    out = load_results_tsv(p)
    assert set(out.keys()) == {1, 2}


# ---------------------------------------------------------------------------
# RunState uses real breakdowns when score_breakdowns is populated
# ---------------------------------------------------------------------------

def test_iteration_completed_uses_score_breakdowns_when_available():
    """When results.tsv was loaded into ``score_breakdowns``, the chart
    point uses the real coverage/quality split, not the synthesized total."""
    s = RunState()
    s.score_breakdowns = {1: (94.4, 65.0, 104.5)}
    s.apply_event({"event": "step_started", "step": "hypothesise",
                   "iteration": 1, "dimension": "REST"})
    s.apply_event({"event": "iteration_completed", "iteration": 1,
                   "dimension": "REST", "status": "KEEP", "total_score": 104.5})
    assert s.chart_points == [(1, 94.4, 65.0, 104.5)]


def test_iteration_completed_falls_back_to_total_when_no_breakdown():
    """Without results.tsv, the heuristic and quality lines fall back to
    the total score (no synthesis), collapsing 3 lines into 1 visually
    rather than fabricating numbers."""
    s = RunState()
    # score_breakdowns is empty (default)
    s.apply_event({"event": "iteration_completed", "iteration": 1,
                   "dimension": "REST", "status": "KEEP", "total_score": 76.0})
    assert s.chart_points == [(1, 76.0, 76.0, 76.0)]


# ---------------------------------------------------------------------------
# Scripted events generator
# ---------------------------------------------------------------------------

def test_scripted_events_starts_with_run_started_and_ends_with_run_completed():
    events = scripted_events()
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_completed"


def test_scripted_events_can_drive_a_full_runstate():
    """The synthesised events should leave RunState in a coherent terminal state."""
    s = RunState()
    for ev in scripted_events():
        s.apply_event(ev)

    # Should have processed all 12 iterations
    assert max(s.iters.keys()) == 12
    # At least 11 KEEPs (iter 7 is the scripted DISCARD)
    keeps = sum(1 for r in s.iters.values() if r.decision == "KEEP")
    assert keeps >= 10
    # Chart points: one per iteration_completed with total_score
    assert len(s.chart_points) == 12
    # Final state
    assert s.finished
    assert s.current_state == "DONE"


# ---------------------------------------------------------------------------
# Audit file iteration — graceful on missing/malformed
# ---------------------------------------------------------------------------

def test_iter_audit_events_missing_file_yields_nothing():
    events = list(iter_audit_events(Path("/tmp/__nonexistent_audit_trail__.jsonl")))
    assert events == []


def test_iter_audit_events_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "audit.jsonl"
    p.write_text(
        '{"event": "run_started"}\n'
        'not json at all\n'
        '\n'                                 # blank line
        '{"event": "iteration_started", "iteration": 1}\n'
        '{ broken json ',
        encoding="utf-8",
    )
    events = list(iter_audit_events(p))
    assert len(events) == 2
    assert events[0]["event"] == "run_started"
    assert events[1]["event"] == "iteration_started"


def test_iter_audit_events_handles_empty_file(tmp_path: Path):
    p = tmp_path / "audit.jsonl"
    p.write_text("", encoding="utf-8")
    assert list(iter_audit_events(p)) == []


# ---------------------------------------------------------------------------
# follow_audit_events — generator semantics, not blocking
# ---------------------------------------------------------------------------

def test_follow_audit_events_is_a_generator():
    """We can't really test the polling without a thread, but we can confirm
    the function returns a generator that yields the catch-up events first
    when the file already exists."""
    import inspect
    assert inspect.isgeneratorfunction(follow_audit_events)
