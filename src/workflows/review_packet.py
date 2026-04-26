"""Structured review packets for HITL workflow pauses.

Emitted as *hitl_review_packet.json* in the run output directory whenever a
workflow pauses for human input.  The packet gives operators a consolidated,
machine-readable view of:

- which gate fired and at what cycle (sequence)
- current workflow state and convergence progress
- open issues in the registry (valid, deferred, open — not stale/resolved)
- candidate decisions: the system's suggested answers for each pending question
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REVIEW_PACKET_FILENAME = "hitl_review_packet.json"


# ---------------------------------------------------------------------------
# Sub-record types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateSummary:
    """Metadata about the gate that triggered the pause."""

    workflow: str
    target: str
    gate_trigger: str
    sequence: int


@dataclass(frozen=True)
class OpenIssue:
    """A condensed view of one issue registry entry."""

    id: str
    description: str
    raised_by: str
    cycle: int
    section_ref: str
    status: str


@dataclass(frozen=True)
class CandidateDecision:
    """The system's suggested resolution for one pending question."""

    issue_id: str
    question: str
    suggested_answer: str
    context: str


# ---------------------------------------------------------------------------
# Review packet
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewPacket:
    """Full structured review packet emitted at a workflow pause.

    Attributes
    ----------
    created_at:
        UTC ISO-8601 timestamp when the packet was built.
    workflow:
        The workflow that paused — ``"refine"`` or ``"plan"``.
    cycle:
        The convergence cycle at which the pause occurred.
    gate:
        Metadata about the gate that fired.
    workflow_state:
        Semantic state at pause time — always ``"paused_for_human"``.
    consecutive_clean_cycles:
        How many consecutive clean cycles preceded the pause.
    open_issues:
        Issues from the registry whose status is not ``stale`` or
        ``resolved`` — i.e., issues the operator may need to consider.
    candidate_decisions:
        System-suggested answers for each pending human question.
    """

    created_at: str
    workflow: str
    cycle: int
    gate: GateSummary
    workflow_state: str
    consecutive_clean_cycles: int
    open_issues: list[OpenIssue]
    candidate_decisions: list[CandidateDecision]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

_EXCLUDED_STATUSES = frozenset({"stale", "resolved"})


def build_review_packet(
    workflow: str,
    cycle: int,
    consecutive_clean_cycles: int,
    open_issues: list[Any],
    pending_requests: list[Any],
) -> ReviewPacket:
    """Build a :class:`ReviewPacket` from current loop state.

    Parameters
    ----------
    workflow:
        The workflow name — ``"refine"`` or ``"plan"``.
    cycle:
        Current convergence cycle number, used as the gate sequence.
    consecutive_clean_cycles:
        Number of clean cycles before the pause.
    open_issues:
        Full issue registry (list of Issue-like objects with ``id``,
        ``description``, ``raised_by``, ``cycle``, ``section_ref``,
        ``status`` attributes).  Stale and resolved entries are filtered out.
    pending_requests:
        Pending :class:`~src.hitl.HumanInputRequest` objects (``issue_id``,
        ``question``, ``suggested_answer``, ``context``).
    """
    gate = GateSummary(
        workflow=workflow,
        target="verifier",
        gate_trigger="after",
        sequence=cycle,
    )
    filtered_issues = [
        OpenIssue(
            id=i.id,
            description=i.description,
            raised_by=i.raised_by,
            cycle=i.cycle,
            section_ref=i.section_ref,
            status=i.status,
        )
        for i in open_issues
        if i.status not in _EXCLUDED_STATUSES
    ]
    decisions = [
        CandidateDecision(
            issue_id=r.issue_id,
            question=r.question,
            suggested_answer=r.suggested_answer,
            context=r.context,
        )
        for r in pending_requests
    ]
    return ReviewPacket(
        created_at=datetime.now(timezone.utc).isoformat(),
        workflow=workflow,
        cycle=cycle,
        gate=gate,
        workflow_state="paused_for_human",
        consecutive_clean_cycles=consecutive_clean_cycles,
        open_issues=filtered_issues,
        candidate_decisions=decisions,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def write_review_packet(packet: ReviewPacket, path: Path) -> None:
    """Serialise *packet* as indented JSON and write it to *path*.

    Overwrites any existing file at *path*.
    """
    path.write_text(json.dumps(packet.to_dict(), indent=2), encoding="utf-8")
