"""Tests for src/workflows/decisions.py — shared decision vocabulary."""
from __future__ import annotations

import pytest

from src.workflows.decisions import (
    ACCEPTED,
    ABNORMAL,
    CRITIQUE_STATUSES,
    CritiqueStatus,
    ISSUE_STATUSES,
    ITERATION_OUTCOMES,
    IssueStatus,
    IterationDecision,
    PENDING,
    REJECTED,
    WORKFLOW_DECISION_TYPES,
)


# ---------------------------------------------------------------------------
# IterationDecision
# ---------------------------------------------------------------------------


class TestIterationDecision:
    def test_keep_value(self):
        assert IterationDecision.KEEP == "keep"

    def test_discard_value(self):
        assert IterationDecision.DISCARD == "discard"

    def test_crash_value(self):
        assert IterationDecision.CRASH == "crash"

    def test_is_str(self):
        assert isinstance(IterationDecision.KEEP, str)
        assert isinstance(IterationDecision.DISCARD, str)
        assert isinstance(IterationDecision.CRASH, str)

    def test_string_comparison_works(self):
        # existing code does: status == "keep" — must still work
        assert IterationDecision.KEEP == "keep"
        assert "keep" == IterationDecision.KEEP

    def test_all_members(self):
        values = {d.value for d in IterationDecision}
        assert values == {"keep", "discard", "crash"}

    def test_iteration_outcomes_frozenset(self):
        assert ITERATION_OUTCOMES == {"keep", "discard", "crash"}
        assert isinstance(ITERATION_OUTCOMES, frozenset)


# ---------------------------------------------------------------------------
# CritiqueStatus
# ---------------------------------------------------------------------------


class TestCritiqueStatus:
    def test_valid_value(self):
        assert CritiqueStatus.VALID == "valid"

    def test_stale_value(self):
        assert CritiqueStatus.STALE == "stale"

    def test_deferred_value(self):
        assert CritiqueStatus.DEFERRED == "deferred"

    def test_is_str(self):
        assert isinstance(CritiqueStatus.VALID, str)

    def test_all_members(self):
        values = {s.value for s in CritiqueStatus}
        assert values == {"valid", "stale", "deferred"}

    def test_critique_statuses_frozenset(self):
        assert CRITIQUE_STATUSES == {"valid", "stale", "deferred"}
        assert isinstance(CRITIQUE_STATUSES, frozenset)


# ---------------------------------------------------------------------------
# IssueStatus
# ---------------------------------------------------------------------------


class TestIssueStatus:
    def test_open_value(self):
        assert IssueStatus.OPEN == "open"

    def test_valid_value(self):
        assert IssueStatus.VALID == "valid"

    def test_stale_value(self):
        assert IssueStatus.STALE == "stale"

    def test_deferred_value(self):
        assert IssueStatus.DEFERRED == "deferred"

    def test_resolved_value(self):
        assert IssueStatus.RESOLVED == "resolved"

    def test_is_str(self):
        assert isinstance(IssueStatus.VALID, str)

    def test_all_members(self):
        values = {s.value for s in IssueStatus}
        assert values == {"open", "valid", "stale", "deferred", "resolved"}

    def test_issue_statuses_frozenset(self):
        assert ISSUE_STATUSES == {"open", "valid", "stale", "deferred", "resolved"}
        assert isinstance(ISSUE_STATUSES, frozenset)


# ---------------------------------------------------------------------------
# Semantic groupings
# ---------------------------------------------------------------------------


class TestSemanticGroups:
    def test_accepted_contains_keep_and_valid(self):
        assert "keep" in ACCEPTED
        assert "valid" in ACCEPTED

    def test_rejected_contains_discard_and_stale(self):
        assert "discard" in REJECTED
        assert "stale" in REJECTED

    def test_pending_contains_deferred_and_open(self):
        assert "deferred" in PENDING
        assert "open" in PENDING

    def test_abnormal_contains_crash(self):
        assert "crash" in ABNORMAL

    def test_groups_are_frozensets(self):
        assert isinstance(ACCEPTED, frozenset)
        assert isinstance(REJECTED, frozenset)
        assert isinstance(PENDING, frozenset)
        assert isinstance(ABNORMAL, frozenset)

    def test_groups_are_disjoint(self):
        groups = [ACCEPTED, REJECTED, PENDING, ABNORMAL]
        for i, g1 in enumerate(groups):
            for j, g2 in enumerate(groups):
                if i != j:
                    assert g1.isdisjoint(g2), f"Group {i} and {j} overlap: {g1 & g2}"

    def test_accepted_disjoint_from_rejected(self):
        assert ACCEPTED.isdisjoint(REJECTED)

    def test_all_outcome_strings_covered(self):
        all_terms = ACCEPTED | REJECTED | PENDING | ABNORMAL
        # every known decision string must appear in at least one group
        for val in ITERATION_OUTCOMES | CRITIQUE_STATUSES | ISSUE_STATUSES:
            assert val in all_terms, f"{val!r} not in any semantic group"


# ---------------------------------------------------------------------------
# Cross-mode consistency
# ---------------------------------------------------------------------------


class TestCrossModeConsistency:
    def test_valid_shared_string_consistent(self):
        # "valid" means accepted in both critique and issue contexts
        assert CritiqueStatus.VALID.value == IssueStatus.VALID.value == "valid"
        assert "valid" in ACCEPTED

    def test_stale_shared_string_consistent(self):
        assert CritiqueStatus.STALE.value == IssueStatus.STALE.value == "stale"
        assert "stale" in REJECTED

    def test_deferred_shared_string_consistent(self):
        assert CritiqueStatus.DEFERRED.value == IssueStatus.DEFERRED.value == "deferred"
        assert "deferred" in PENDING

    def test_keep_is_accepted(self):
        assert IterationDecision.KEEP in ACCEPTED

    def test_discard_is_rejected(self):
        assert IterationDecision.DISCARD in REJECTED

    def test_crash_is_abnormal(self):
        assert IterationDecision.CRASH in ABNORMAL


# ---------------------------------------------------------------------------
# Workflow→decision type mapping
# ---------------------------------------------------------------------------


class TestWorkflowDecisionTypes:
    def test_research_maps_to_iteration_decision(self):
        assert WORKFLOW_DECISION_TYPES["research"] is IterationDecision

    def test_refine_maps_to_critique_status(self):
        assert WORKFLOW_DECISION_TYPES["refine"] is CritiqueStatus

    def test_plan_maps_to_critique_status(self):
        assert WORKFLOW_DECISION_TYPES["plan"] is CritiqueStatus

    def test_all_three_modes_present(self):
        assert set(WORKFLOW_DECISION_TYPES.keys()) == {"research", "refine", "plan"}
