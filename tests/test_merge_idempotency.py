"""Regression tests for the merge-findings idempotency guard.

The guard prevents the knowledge_base from doubling when an iteration is
re-run after a crash that landed between the KB write and the iter-md /
results.tsv writes for the same iteration.  See the matching change in
``src/run_state.py::merge_findings``.
"""

from __future__ import annotations

from src.run_state import merge_findings


def _common_args(**overrides):
    base = dict(
        dimension="REST API",
        findings="Some findings about REST.",
        gaps=[],
        knowledge_base="",
        explored_dimensions=[],
        discovered_dimensions=[],
        configured_dimensions=("REST API", "WebSocket"),
    )
    base.update(overrides)
    return base


def test_merge_returns_skip_flag_false_for_first_merge():
    out = merge_findings(**_common_args())
    assert out["skipped_duplicate_merge"] is False
    assert "## REST API" in out["knowledge_base"]
    assert "Some findings about REST." in out["knowledge_base"]
    assert "REST API" in out["explored_dimensions"]


def test_merge_appends_findings_on_first_call():
    out = merge_findings(**_common_args(knowledge_base="# preamble\n"))
    kb = out["knowledge_base"]
    assert kb.count("## REST API") == 1
    assert kb.endswith("Some findings about REST.")


def test_merge_skipped_when_dimension_already_in_kb():
    """Resume after partial completion: KB already has the section, the loop
    re-runs the iteration, the merge MUST not append a second copy."""
    pre_existing_kb = "## REST API\n\nFindings from the previous attempt that survived to disk."
    out = merge_findings(**_common_args(knowledge_base=pre_existing_kb))

    assert out["skipped_duplicate_merge"] is True
    # KB unchanged — no second append
    assert out["knowledge_base"] == pre_existing_kb
    # explored_dimensions still updated (idempotent)
    assert out["explored_dimensions"] == ["REST API"]


def test_merge_skipped_only_for_exact_dimension_header_not_substring():
    """A different dim that happens to share a prefix should NOT trigger the skip."""
    pre_existing_kb = "## REST API: long version\n\nFindings."
    out = merge_findings(**_common_args(
        dimension="REST API",
        knowledge_base=pre_existing_kb,
    ))
    # "## REST API\n" is NOT in the KB — only "## REST API: long version\n"
    assert out["skipped_duplicate_merge"] is False
    assert out["knowledge_base"].count("## REST API") == 2


def test_merge_idempotent_explored_dimensions_no_duplicate_entry():
    """Re-running an already-merged dim must not add the dim twice to explored."""
    pre_existing_kb = "## REST API\n\nFindings."
    out = merge_findings(**_common_args(
        knowledge_base=pre_existing_kb,
        explored_dimensions=["REST API"],
    ))
    assert out["skipped_duplicate_merge"] is True
    assert out["explored_dimensions"] == ["REST API"]


def test_merge_skip_does_not_drop_gap_processing():
    """Skipping the KB append still advances discovered_dimensions for new gaps."""
    pre_existing_kb = "## REST API\n\nFindings."
    out = merge_findings(**_common_args(
        knowledge_base=pre_existing_kb,
        gaps=["fresh-gap-from-rerun"],
    ))
    assert out["skipped_duplicate_merge"] is True
    assert "fresh-gap-from-rerun" in out["discovered_dimensions"]


def test_merge_first_merge_then_second_attempt_idempotent():
    """End-to-end: first call merges, second call with same dim is a no-op."""
    args = _common_args()
    out1 = merge_findings(**args)
    assert out1["skipped_duplicate_merge"] is False
    kb_after_first = out1["knowledge_base"]

    args["knowledge_base"] = kb_after_first
    args["explored_dimensions"] = out1["explored_dimensions"]
    args["discovered_dimensions"] = out1["discovered_dimensions"]
    out2 = merge_findings(**args)

    assert out2["skipped_duplicate_merge"] is True
    assert out2["knowledge_base"] == kb_after_first
    # Section count stable — no doubling
    assert out2["knowledge_base"].count("## REST API") == 1
