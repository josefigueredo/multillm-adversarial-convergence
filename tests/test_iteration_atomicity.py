"""Tests for the sentinel + rollback iteration-atomicity contract.

The contract: a SIGKILL anywhere between ``write_iteration_sentinel`` and
``clear_iteration_sentinel`` MUST be detected and rolled back on resume so
the iteration can be re-attempted without doubling the knowledge base or
leaving orphaned ``iter_NNN.md`` / ``results.tsv`` rows.

See ``docs/plans/iteration-atomicity.md`` for the design rationale.

These tests synthesise on-disk state to simulate each crash window — the
real orchestrator is not invoked.  That keeps the test surface tight and
the cases unambiguous.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.run_state import (
    SENTINEL_PREFIX,
    SENTINEL_SUFFIX,
    _drop_kb_section,
    _drop_last_tsv_row_if_iteration,
    clear_iteration_sentinel,
    resume_state,
    rollback_partial_iterations,
    write_iteration_sentinel,
)


# ---------------------------------------------------------------------------
# Fixture: minimal output-dir layout
# ---------------------------------------------------------------------------

TSV_HEADER = (
    "iteration\ttimestamp\tdimension\tcoverage_score\tquality_score\ttotal_score\t"
    "status\thypothesis\tdiscovered_gaps\tcumulative_cost_usd\n"
)


def _tsv_row(iteration: int, dimension: str, status: str = "keep", total: float = 75.0) -> str:
    return (
        f"{iteration:03d}\t2026-05-07T00:00:00\t{dimension}\t40.0\t60.0\t{total}\t"
        f"{status}\tplaceholder hypothesis\t[]\t0.0\n"
    )


@pytest.fixture
def run_dir(tmp_path: Path):
    iterations = tmp_path / "iterations"
    iterations.mkdir()
    return {
        "iterations_dir": iterations,
        "results_path": tmp_path / "results.tsv",
        "knowledge_base_path": tmp_path / "knowledge_base.md",
    }


# ---------------------------------------------------------------------------
# Sentinel I/O
# ---------------------------------------------------------------------------

def test_write_sentinel_creates_file_with_expected_payload(run_dir):
    sentinel = write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"],
        iteration=5,
        dimension="REST API",
    )
    assert sentinel.exists()
    payload = json.loads(sentinel.read_text(encoding="utf-8"))
    assert payload["iteration"] == 5
    assert payload["dimension"] == "REST API"
    assert payload["kb_section_marker"] == "\n## REST API\n"


def test_clear_sentinel_removes_file(run_dir):
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=7, dimension="X",
    )
    clear_iteration_sentinel(iterations_dir=run_dir["iterations_dir"], iteration=7)
    assert not list(run_dir["iterations_dir"].glob(f"{SENTINEL_PREFIX}*{SENTINEL_SUFFIX}"))


def test_clear_sentinel_idempotent_when_missing(run_dir):
    # No-op, no exception
    clear_iteration_sentinel(iterations_dir=run_dir["iterations_dir"], iteration=99)


# ---------------------------------------------------------------------------
# _drop_kb_section — surgical excision of a single dimension's section
# ---------------------------------------------------------------------------

def test_drop_kb_section_removes_named_section_from_middle(run_dir):
    kb = (
        "# Preamble\n\n"
        "## Foo\n\nFoo findings here.\n\n"
        "## REST API\n\nREST findings to delete.\n\n"
        "## Bar\n\nBar findings.\n"
    )
    new_kb, removed = _drop_kb_section(kb, "\n## REST API\n")
    assert removed
    assert "REST findings to delete" not in new_kb
    assert "Foo findings here" in new_kb
    assert "Bar findings" in new_kb


def test_drop_kb_section_handles_section_at_position_zero(run_dir):
    """A section at offset 0 (no leading \\n) must still be removable."""
    kb = "## REST API\n\nFindings.\n\n## Other\n\nOther stuff.\n"
    new_kb, removed = _drop_kb_section(kb, "\n## REST API\n")
    assert removed
    assert "REST API" not in new_kb
    assert "Other stuff" in new_kb


def test_drop_kb_section_handles_section_at_eof(run_dir):
    """A section that runs to EOF must be removable (no trailing `\\n## `)."""
    kb = "# Preamble\n\n## Foo\n\nKeep.\n\n## REST API\n\nDelete this last section."
    new_kb, removed = _drop_kb_section(kb, "\n## REST API\n")
    assert removed
    assert "Delete this last section" not in new_kb
    assert "Keep." in new_kb


def test_drop_kb_section_no_op_when_marker_absent(run_dir):
    kb = "## A\n\nA stuff.\n"
    new_kb, removed = _drop_kb_section(kb, "\n## REST API\n")
    assert not removed
    assert new_kb == kb


def test_drop_kb_section_does_not_match_prefix_only(run_dir):
    """Dimension names that share a prefix must not collide."""
    kb = "## REST API: long version\n\nDifferent dim.\n\n## Other\n\nOther.\n"
    new_kb, removed = _drop_kb_section(kb, "\n## REST API\n")
    # The marker is "\n## REST API\n" (with trailing \n) — won't match "REST API: long version"
    assert not removed
    assert new_kb == kb


# ---------------------------------------------------------------------------
# _drop_last_tsv_row_if_iteration
# ---------------------------------------------------------------------------

def test_drop_last_tsv_row_removes_when_match(run_dir):
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(1, "A") + _tsv_row(2, "B"))
    assert _drop_last_tsv_row_if_iteration(run_dir["results_path"], 2) is True
    final = run_dir["results_path"].read_text(encoding="utf-8")
    assert "002" not in final.splitlines()[-1]
    assert "001" in final


def test_drop_last_tsv_row_no_op_when_iteration_mismatches(run_dir):
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(1, "A") + _tsv_row(2, "B"))
    assert _drop_last_tsv_row_if_iteration(run_dir["results_path"], 5) is False
    # File unchanged
    assert run_dir["results_path"].read_text().count("\n") == 3  # header + 2 rows


def test_drop_last_tsv_row_no_op_on_header_only(run_dir):
    run_dir["results_path"].write_text(TSV_HEADER)
    assert _drop_last_tsv_row_if_iteration(run_dir["results_path"], 1) is False


def test_drop_last_tsv_row_no_op_when_file_missing(run_dir):
    assert _drop_last_tsv_row_if_iteration(run_dir["results_path"], 1) is False


# ---------------------------------------------------------------------------
# rollback_partial_iterations — the integration tests
# ---------------------------------------------------------------------------

def _write_kb(run_dir, content):
    run_dir["knowledge_base_path"].write_text(content, encoding="utf-8")


def test_rollback_no_sentinels_returns_empty(run_dir):
    result = rollback_partial_iterations(**run_dir)
    assert result == []


def test_rollback_sentinel_only_no_side_effects(run_dir):
    """Crash window 2: sentinel written, no other writes happened yet."""
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=3, dimension="X",
    )
    result = rollback_partial_iterations(**run_dir)
    assert len(result) == 1
    assert result[0]["iteration"] == 3
    assert result[0]["undone"] == []   # nothing to undo
    # Sentinel itself removed
    assert not list(run_dir["iterations_dir"].glob(f"{SENTINEL_PREFIX}*{SENTINEL_SUFFIX}"))


def test_rollback_kb_write_only(run_dir):
    """Crash window 3: KB section written, iter_md / sidecar / tsv NOT yet."""
    _write_kb(run_dir, "## REST API\n\nFindings about REST.")
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="REST API",
    )
    result = rollback_partial_iterations(**run_dir)
    assert result[0]["undone"] == ["kb_section"]
    # KB no longer contains the section
    assert "## REST API" not in run_dir["knowledge_base_path"].read_text()


def test_rollback_kb_and_iter_md(run_dir):
    """Crash window 4: KB + iter_md, sidecar / tsv NOT yet."""
    _write_kb(run_dir, "## REST API\n\nFindings about REST.")
    (run_dir["iterations_dir"] / "iter_002.md").write_text("# iter 2 md")
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="REST API",
    )
    result = rollback_partial_iterations(**run_dir)
    assert set(result[0]["undone"]) == {"kb_section", "iter_md"}
    assert not (run_dir["iterations_dir"] / "iter_002.md").exists()
    assert "## REST API" not in run_dir["knowledge_base_path"].read_text()


def test_rollback_full_window_kb_iter_md_tsv(run_dir):
    """Crash window 5: all three side effects present."""
    _write_kb(run_dir, "## REST API\n\nFindings about REST.")
    (run_dir["iterations_dir"] / "iter_002.md").write_text("# iter 2 md")
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(1, "Foo") + _tsv_row(2, "REST API"))
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="REST API",
    )
    result = rollback_partial_iterations(**run_dir)
    assert set(result[0]["undone"]) == {"kb_section", "iter_md", "tsv_row"}
    # All three undone
    assert not (run_dir["iterations_dir"] / "iter_002.md").exists()
    assert "## REST API" not in run_dir["knowledge_base_path"].read_text()
    final_tsv = run_dir["results_path"].read_text()
    assert "001" in final_tsv  # iter 1 row preserved
    assert "REST API" not in final_tsv  # iter 2 row gone


def test_rollback_post_compress_completed_iteration_no_sentinel_left(run_dir):
    """Crash window 6: all 4 writes completed, sentinel cleared, then compress
    crashed. There's no sentinel to find, so rollback is a no-op."""
    _write_kb(run_dir, "## REST API\n\nFindings.")
    (run_dir["iterations_dir"] / "iter_002.md").write_text("# iter 2 md")
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(2, "REST API"))
    # No sentinel — clear ran successfully before the compress crash.

    result = rollback_partial_iterations(**run_dir)
    assert result == []
    # All side effects preserved
    assert (run_dir["iterations_dir"] / "iter_002.md").exists()
    assert "## REST API" in run_dir["knowledge_base_path"].read_text()


def test_rollback_multiple_sentinels_handled_independently(run_dir):
    """Two simultaneous sentinels (very unusual, but defensible) → both rolled back."""
    _write_kb(run_dir, "## A\n\nA findings.\n\n## B\n\nB findings.")
    (run_dir["iterations_dir"] / "iter_002.md").write_text("md A")
    (run_dir["iterations_dir"] / "iter_003.md").write_text("md B")
    write_iteration_sentinel(iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="A")
    write_iteration_sentinel(iterations_dir=run_dir["iterations_dir"], iteration=3, dimension="B")

    result = rollback_partial_iterations(**run_dir)
    assert len(result) == 2
    iters = sorted(r["iteration"] for r in result)
    assert iters == [2, 3]
    # Both md files removed
    assert not (run_dir["iterations_dir"] / "iter_002.md").exists()
    assert not (run_dir["iterations_dir"] / "iter_003.md").exists()
    # KB has neither section
    final_kb = run_dir["knowledge_base_path"].read_text()
    assert "## A" not in final_kb
    assert "## B" not in final_kb


def test_rollback_dimension_no_longer_in_kb_succeeds(run_dir):
    """Sentinel for a dim whose section was already removed (e.g., by compress
    rewriting the KB) must still rollback the iter_md and tsv parts."""
    _write_kb(run_dir, "compressed summary that no longer contains the original headers.")
    (run_dir["iterations_dir"] / "iter_004.md").write_text("# iter 4 md")
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(4, "REST API"))
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=4, dimension="REST API",
    )
    result = rollback_partial_iterations(**run_dir)
    assert set(result[0]["undone"]) == {"iter_md", "tsv_row"}
    # KB unchanged because there was nothing to remove
    assert "compressed summary" in run_dir["knowledge_base_path"].read_text()


def test_rollback_corrupt_sentinel_removed_silently(run_dir):
    """A sentinel with malformed JSON shouldn't crash the resume — just remove it."""
    bad = run_dir["iterations_dir"] / f"{SENTINEL_PREFIX}005{SENTINEL_SUFFIX}"
    bad.write_text("{ not valid json", encoding="utf-8")
    result = rollback_partial_iterations(**run_dir)
    assert result == []  # corrupt sentinel produces no rollback descriptor
    assert not bad.exists()  # but the file is removed so it doesn't fire again


# ---------------------------------------------------------------------------
# resume_state integration — rollback runs first, returns rollbacks key
# ---------------------------------------------------------------------------

def test_resume_state_runs_rollback_before_counting(run_dir):
    """A crash that left an iter_md file + sentinel must NOT count toward
    resume's iteration counter — the iter_md is rolled back first."""
    _write_kb(run_dir, "## REST API\n\nFindings.")
    (run_dir["iterations_dir"] / "iter_001.md").write_text("# completed iter 1")
    (run_dir["iterations_dir"] / "iter_002.md").write_text("# crashed iter 2")
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(1, "Foo") + _tsv_row(2, "REST API"))
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="REST API",
    )

    out = resume_state(
        **run_dir,
        configured_dimensions=("REST API", "Foo"),
        max_attempts_per_dimension=3,
    )
    # iter_002 was rolled back; only iter_001 remains → iteration counter = 1
    assert out["iteration"] == 1
    # rollback descriptor surfaced
    assert len(out["rollbacks"]) == 1
    assert out["rollbacks"][0]["iteration"] == 2
    # KB no longer contains the rolled-back section
    assert "## REST API" not in run_dir["knowledge_base_path"].read_text()


def test_resume_state_no_sentinel_returns_empty_rollbacks(run_dir):
    out = resume_state(
        **run_dir,
        configured_dimensions=(),
        max_attempts_per_dimension=3,
    )
    assert out["rollbacks"] == []
    assert out["iteration"] == 0


# ---------------------------------------------------------------------------
# End-to-end: simulate a crash + resume + re-attempt → no doubling
# ---------------------------------------------------------------------------

def test_end_to_end_crash_and_resume_no_doubling(run_dir):
    """Full lifecycle: iter 2 KEEP writes the sentinel, writes the KB section,
    then SIGKILL before any other write.  On resume, rollback fires, KB is
    restored.  A re-attempt of iter 2 produces a single section, not two."""
    # Setup: iter 1 already complete on disk
    _write_kb(run_dir, "## Foo\n\nFoo findings.")
    (run_dir["iterations_dir"] / "iter_001.md").write_text("# iter 1")
    run_dir["results_path"].write_text(TSV_HEADER + _tsv_row(1, "Foo"))

    # Iter 2 starts: sentinel written, KB section appended, then SIGKILL.
    write_iteration_sentinel(
        iterations_dir=run_dir["iterations_dir"], iteration=2, dimension="REST API",
    )
    kb_now = run_dir["knowledge_base_path"].read_text()
    run_dir["knowledge_base_path"].write_text(
        kb_now + "\n\n## REST API\n\nfirst-attempt findings.",
    )

    # Resume: rollback should remove the KB section and the sentinel.
    out = resume_state(
        **run_dir,
        configured_dimensions=("Foo", "REST API"),
        max_attempts_per_dimension=3,
    )
    assert len(out["rollbacks"]) == 1
    final_kb = run_dir["knowledge_base_path"].read_text()
    # Foo section preserved, REST API section gone
    assert "## Foo" in final_kb
    assert "## REST API" not in final_kb
    assert "first-attempt findings" not in final_kb

    # Now simulate the re-attempt: the iter merges its (new) findings.
    final_kb = run_dir["knowledge_base_path"].read_text()
    run_dir["knowledge_base_path"].write_text(
        final_kb + "\n\n## REST API\n\nsecond-attempt findings.",
    )
    final_kb = run_dir["knowledge_base_path"].read_text()

    # Exactly one REST API section, with the new findings only.
    assert final_kb.count("## REST API") == 1
    assert "second-attempt findings" in final_kb
    assert "first-attempt findings" not in final_kb
