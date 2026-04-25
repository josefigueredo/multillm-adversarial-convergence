"""Shared decision vocabulary for research, refine, and plan workflows.

This module defines canonical str-enum types for the outcome/status strings
scattered across the three runtime modes, semantic groupings that normalize
decision meaning across modes, and a mode→type mapping for introspection.

Decision domains
----------------
- ``IterationDecision`` — research-mode per-iteration outcomes (keep/discard/crash)
- ``CritiqueStatus``   — refine/plan critique status after verifier review
- ``IssueStatus``      — refine/plan issue-tracker lifecycle states

Semantic groupings
------------------
Four cross-mode semantic buckets make it possible to reason about outcomes
without knowing which mode produced them:

- ``ACCEPTED``  — item was accepted / kept (keep, valid)
- ``REJECTED``  — item was discarded / no longer applicable (discard, stale)
- ``PENDING``   — item awaits further work or a human decision (deferred, open)
- ``ABNORMAL``  — item ended due to an unrecoverable error (crash)
"""
from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Enum types
# ---------------------------------------------------------------------------


class IterationDecision(str, Enum):
    """Research-mode outcome of a single hypothesis/execute/score cycle."""

    KEEP = "keep"
    DISCARD = "discard"
    CRASH = "crash"


class CritiqueStatus(str, Enum):
    """Refine/plan mode: status of a critique after verifier review."""

    VALID = "valid"
    STALE = "stale"
    DEFERRED = "deferred"


class IssueStatus(str, Enum):
    """Refine/plan mode: full lifecycle status of a tracked issue."""

    OPEN = "open"
    VALID = "valid"
    STALE = "stale"
    DEFERRED = "deferred"
    RESOLVED = "resolved"


# ---------------------------------------------------------------------------
# Convenience frozensets (for membership tests and validation)
# ---------------------------------------------------------------------------

ITERATION_OUTCOMES: frozenset[str] = frozenset(d.value for d in IterationDecision)
CRITIQUE_STATUSES: frozenset[str] = frozenset(s.value for s in CritiqueStatus)
ISSUE_STATUSES: frozenset[str] = frozenset(s.value for s in IssueStatus)

# ---------------------------------------------------------------------------
# Semantic groupings — cross-mode normalization
# ---------------------------------------------------------------------------

ACCEPTED: frozenset[str] = frozenset({"keep", "valid", "resolved"})
REJECTED: frozenset[str] = frozenset({"discard", "stale"})
PENDING: frozenset[str] = frozenset({"deferred", "open"})
ABNORMAL: frozenset[str] = frozenset({"crash"})

# ---------------------------------------------------------------------------
# Workflow-mode → primary decision type
# ---------------------------------------------------------------------------

WORKFLOW_DECISION_TYPES: dict[str, type] = {
    "research": IterationDecision,
    "refine": CritiqueStatus,
    "plan": CritiqueStatus,
}


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def classify_iteration_decision(
    status: str,
    default: IterationDecision | None = None,
) -> IterationDecision:
    """Return the ``IterationDecision`` for *status*.

    If *status* is not a recognised value and *default* is given, *default*
    is returned instead.  Without a default an unrecognised value raises
    ``ValueError``.
    """
    try:
        return IterationDecision(status)
    except ValueError:
        if default is not None:
            return default
        raise


def classify_critique_status(
    status: str,
    default: CritiqueStatus = CritiqueStatus.STALE,
) -> CritiqueStatus:
    """Return the ``CritiqueStatus`` for *status*.

    Unknown model-produced values fall back to *default* (``STALE`` by
    convention: not actionable but not a crash).
    """
    try:
        return CritiqueStatus(status)
    except ValueError:
        return default


def classify_issue_status(
    status: str,
    default: IssueStatus = IssueStatus.OPEN,
) -> IssueStatus:
    """Return the ``IssueStatus`` for *status*.

    Unknown values fall back to *default* (``OPEN`` by convention: not yet
    classified).
    """
    try:
        return IssueStatus(status)
    except ValueError:
        return default


def semantic_group(status: str) -> str:
    """Return the cross-mode semantic group name for a decision status string.

    Returns one of ``"accepted"``, ``"rejected"``, ``"pending"``, or
    ``"abnormal"``.  Raises ``ValueError`` for unknown strings.
    """
    if status in ACCEPTED:
        return "accepted"
    if status in REJECTED:
        return "rejected"
    if status in PENDING:
        return "pending"
    if status in ABNORMAL:
        return "abnormal"
    raise ValueError(f"Unknown decision status: {status!r}")
