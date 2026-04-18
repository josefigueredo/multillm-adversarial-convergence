"""Human-in-the-loop data structures and collection helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


class DeferReason:
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_RESEARCH = "needs_research"
    HUMAN_REQUIRED = "human_required"


@dataclass
class HumanInputRequest:
    """A question the Verifier could not resolve from the document alone."""

    issue_id: str
    question: str
    context: str
    suggested_answer: str
    cycle: int


@dataclass
class HumanDecision:
    """A resolved human answer for a deferred issue."""

    issue_id: str
    question: str
    answer: str
    answered_at: str
    answered_by: str  # "human" | "auto-confirmed"


def collect_interactive(requests: list[HumanInputRequest]) -> list[HumanDecision]:
    """Prompt the operator for each pending question and collect answers.

    Pressing Enter accepts the Verifier's suggested_answer (answered_by=
    'auto-confirmed'). Typing a non-empty string overrides it (answered_by='human').
    """
    decisions: list[HumanDecision] = []
    total = len(requests)
    print(f"\n[refine] {total} question(s) require your input before proceeding.\n")
    for i, req in enumerate(requests, 1):
        print(f"{'─' * 50}")
        print(f"Question {i} of {total}  [{req.issue_id}]")
        print(f"{'─' * 50}")
        print(f"Context: {req.context}")
        print(f"Issue: {req.question}\n")
        print(f"Suggested answer: {req.suggested_answer}\n")
        raw = input("Press Enter to accept, or type your answer: ").strip()
        if raw:
            answer = raw
            answered_by = "human"
        else:
            answer = req.suggested_answer
            answered_by = "auto-confirmed"
        decisions.append(HumanDecision(
            issue_id=req.issue_id,
            question=req.question,
            answer=answer,
            answered_at=datetime.now(timezone.utc).isoformat(),
            answered_by=answered_by,
        ))
    print("\n[refine] Answers recorded. Resuming.\n")
    return decisions


def write_pending_questions(requests: list[HumanInputRequest], path: Path) -> None:
    """Write pending questions to JSON for async / CI mode."""
    path.write_text(
        json.dumps([asdict(r) for r in requests], indent=2),
        encoding="utf-8",
    )


def load_human_decisions(path: Path) -> list[HumanDecision]:
    """Load human decisions from a JSON file. Returns [] if file is missing."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [HumanDecision(**item) for item in raw]


def append_human_decisions(decisions: list[HumanDecision], path: Path) -> None:
    """Append decisions to the audit-trail JSON file (creates if missing)."""
    existing = load_human_decisions(path)
    existing.extend(decisions)
    path.write_text(
        json.dumps([asdict(d) for d in existing], indent=2),
        encoding="utf-8",
    )
