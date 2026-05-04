from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.policy.hitl import (
    DeferReason,
    HumanDecision,
    HumanInputRequest,
    append_human_decisions,
    collect_interactive,
    load_human_decisions,
    write_pending_questions,
)


def _req(issue_id: str = "I-01") -> HumanInputRequest:
    return HumanInputRequest(
        issue_id=issue_id,
        question="Which deployment model?",
        context="§5.1 — account topology",
        suggested_answer="One account per tenant",
        cycle=1,
    )


def test_collect_interactive_accepts_suggestion(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    decisions = collect_interactive([_req()])
    assert len(decisions) == 1
    assert decisions[0].answer == "One account per tenant"
    assert decisions[0].answered_by == "auto-confirmed"
    assert decisions[0].issue_id == "I-01"


def test_collect_interactive_overrides_answer(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "custom answer")
    decisions = collect_interactive([_req()])
    assert decisions[0].answer == "custom answer"
    assert decisions[0].answered_by == "human"


def test_collect_interactive_multiple(monkeypatch):
    answers = iter(["", "my answer"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    decisions = collect_interactive([_req("I-01"), _req("I-02")])
    assert len(decisions) == 2
    assert decisions[0].answered_by == "auto-confirmed"
    assert decisions[1].answered_by == "human"


def test_write_pending_questions(tmp_path):
    req = _req()
    write_pending_questions([req], tmp_path / "pending.json")
    data = json.loads((tmp_path / "pending.json").read_text())
    assert isinstance(data, list)
    assert data[0]["issue_id"] == "I-01"
    assert data[0]["question"] == "Which deployment model?"
    assert data[0]["suggested_answer"] == "One account per tenant"


def test_load_human_decisions_returns_empty_when_missing(tmp_path):
    decisions = load_human_decisions(tmp_path / "nonexistent.json")
    assert decisions == []


def test_load_human_decisions_reads_existing(tmp_path):
    p = tmp_path / "decisions.json"
    p.write_text(json.dumps([
        {
            "issue_id": "I-01",
            "question": "Q?",
            "answer": "A",
            "answered_at": "2026-04-17T10:00:00+00:00",
            "answered_by": "human",
        }
    ]))
    decisions = load_human_decisions(p)
    assert len(decisions) == 1
    assert decisions[0].issue_id == "I-01"
    assert decisions[0].answer == "A"


def test_append_human_decisions(tmp_path):
    path = tmp_path / "decisions.json"
    d1 = HumanDecision(issue_id="I-01", question="Q1", answer="A1",
                        answered_at="2026-04-17T10:00:00+00:00", answered_by="human")
    append_human_decisions([d1], path)
    d2 = HumanDecision(issue_id="I-02", question="Q2", answer="A2",
                        answered_at="2026-04-17T11:00:00+00:00", answered_by="auto-confirmed")
    append_human_decisions([d2], path)
    all_decisions = load_human_decisions(path)
    assert len(all_decisions) == 2
    assert all_decisions[0].issue_id == "I-01"
    assert all_decisions[1].issue_id == "I-02"


def test_defer_reason_constants():
    assert DeferReason.OUT_OF_SCOPE == "out_of_scope"
    assert DeferReason.NEEDS_RESEARCH == "needs_research"
    assert DeferReason.HUMAN_REQUIRED == "human_required"
