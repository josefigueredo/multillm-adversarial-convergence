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
