"""Tests for MM08 Step 4: structured HITL review packets."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.workflows.review_packet import (
    REVIEW_PACKET_FILENAME,
    CandidateDecision,
    GateSummary,
    OpenIssue,
    ReviewPacket,
    build_review_packet,
    write_review_packet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(id="I-01", status="valid", **kwargs):
    issue = MagicMock()
    issue.id = id
    issue.description = kwargs.get("description", "Test issue")
    issue.raised_by = kwargs.get("raised_by", "challenger")
    issue.cycle = kwargs.get("cycle", 1)
    issue.section_ref = kwargs.get("section_ref", "§1")
    issue.status = status
    return issue


def _make_request(issue_id="I-01", question="Q?", suggested_answer="A", context="ctx"):
    req = MagicMock()
    req.issue_id = issue_id
    req.question = question
    req.suggested_answer = suggested_answer
    req.context = context
    return req


# ---------------------------------------------------------------------------
# GateSummary
# ---------------------------------------------------------------------------

def test_gate_summary_fields():
    gate = GateSummary(
        workflow="refine", target="verifier", gate_trigger="after",
        target_type="phase", sequence=3,
    )
    assert gate.workflow == "refine"
    assert gate.target == "verifier"
    assert gate.gate_trigger == "after"
    assert gate.target_type == "phase"
    assert gate.sequence == 3


def test_gate_summary_is_frozen():
    gate = GateSummary(
        workflow="refine", target="verifier", gate_trigger="after",
        target_type="phase", sequence=1,
    )
    with pytest.raises((AttributeError, TypeError)):
        gate.workflow = "plan"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# OpenIssue
# ---------------------------------------------------------------------------

def test_open_issue_fields():
    issue = OpenIssue(
        id="I-02", description="desc", raised_by="challenger",
        cycle=2, section_ref="§3", status="deferred",
    )
    assert issue.id == "I-02"
    assert issue.status == "deferred"


def test_open_issue_is_frozen():
    issue = OpenIssue(id="I-01", description="d", raised_by="c", cycle=1, section_ref="§1", status="valid")
    with pytest.raises((AttributeError, TypeError)):
        issue.status = "resolved"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CandidateDecision
# ---------------------------------------------------------------------------

def test_candidate_decision_fields():
    cd = CandidateDecision(
        issue_id="I-01", question="Q?", suggested_answer="A!", context="ctx"
    )
    assert cd.issue_id == "I-01"
    assert cd.suggested_answer == "A!"


def test_candidate_decision_is_frozen():
    cd = CandidateDecision(issue_id="I-01", question="Q", suggested_answer="A", context="c")
    with pytest.raises((AttributeError, TypeError)):
        cd.suggested_answer = "B"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_review_packet
# ---------------------------------------------------------------------------

def test_build_review_packet_basic_structure():
    packet = build_review_packet(
        workflow="refine",
        cycle=2,
        consecutive_clean_cycles=0,
        open_issues=[],
        pending_requests=[],
    )
    assert isinstance(packet, ReviewPacket)
    assert packet.workflow == "refine"
    assert packet.cycle == 2
    assert packet.consecutive_clean_cycles == 0
    assert packet.workflow_state == "paused_for_human"


def test_build_review_packet_gate_fields():
    packet = build_review_packet(
        workflow="plan",
        cycle=5,
        consecutive_clean_cycles=1,
        open_issues=[],
        pending_requests=[],
        target="verifier",
        gate_trigger="after",
        target_type="phase",
    )
    assert packet.gate.workflow == "plan"
    assert packet.gate.target == "verifier"
    assert packet.gate.gate_trigger == "after"
    assert packet.gate.target_type == "phase"
    assert packet.gate.sequence == 5


def test_build_review_packet_non_verifier_target():
    packet = build_review_packet(
        workflow="refine",
        cycle=2,
        consecutive_clean_cycles=0,
        open_issues=[],
        pending_requests=[],
        target="builder",
        gate_trigger="before",
        target_type="phase",
    )
    assert packet.gate.target == "builder"
    assert packet.gate.gate_trigger == "before"


def test_build_review_packet_checkpoint_target():
    packet = build_review_packet(
        workflow="refine",
        cycle=3,
        consecutive_clean_cycles=2,
        open_issues=[],
        pending_requests=[],
        target="convergence",
        gate_trigger="after",
        target_type="checkpoint",
    )
    assert packet.gate.target == "convergence"
    assert packet.gate.target_type == "checkpoint"


def test_build_review_packet_default_gate_is_verifier_after_phase():
    packet = build_review_packet(
        workflow="refine",
        cycle=1,
        consecutive_clean_cycles=0,
        open_issues=[],
        pending_requests=[],
    )
    assert packet.gate.target == "verifier"
    assert packet.gate.gate_trigger == "after"
    assert packet.gate.target_type == "phase"


def test_build_review_packet_filters_stale_issues():
    issues = [
        _make_issue("I-01", status="valid"),
        _make_issue("I-02", status="stale"),
        _make_issue("I-03", status="deferred"),
    ]
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=issues, pending_requests=[],
    )
    ids = [i.id for i in packet.open_issues]
    assert "I-01" in ids
    assert "I-03" in ids
    assert "I-02" not in ids


def test_build_review_packet_filters_resolved_issues():
    issues = [
        _make_issue("I-01", status="valid"),
        _make_issue("I-02", status="resolved"),
    ]
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=issues, pending_requests=[],
    )
    ids = [i.id for i in packet.open_issues]
    assert "I-01" in ids
    assert "I-02" not in ids


def test_build_review_packet_candidate_decisions_from_requests():
    requests = [
        _make_request("I-01", "Q1?", "Answer1", "context1"),
        _make_request("I-02", "Q2?", "Answer2", "context2"),
    ]
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=requests,
    )
    assert len(packet.candidate_decisions) == 2
    assert packet.candidate_decisions[0].issue_id == "I-01"
    assert packet.candidate_decisions[0].suggested_answer == "Answer1"
    assert packet.candidate_decisions[1].issue_id == "I-02"
    assert packet.candidate_decisions[1].suggested_answer == "Answer2"


def test_build_review_packet_empty_inputs():
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    assert packet.open_issues == []
    assert packet.candidate_decisions == []


def test_build_review_packet_timestamp_is_set():
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    assert packet.created_at != ""
    assert "T" in packet.created_at  # ISO 8601 format


def test_build_review_packet_all_issue_statuses_except_stale_resolved():
    issues = [
        _make_issue("I-01", status="valid"),
        _make_issue("I-02", status="deferred"),
        _make_issue("I-03", status="open"),
        _make_issue("I-04", status="stale"),
        _make_issue("I-05", status="resolved"),
    ]
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=issues, pending_requests=[],
    )
    ids = {i.id for i in packet.open_issues}
    assert ids == {"I-01", "I-02", "I-03"}


# ---------------------------------------------------------------------------
# ReviewPacket.to_dict
# ---------------------------------------------------------------------------

def test_review_packet_to_dict_structure():
    packet = build_review_packet(
        workflow="refine", cycle=2, consecutive_clean_cycles=0,
        open_issues=[_make_issue("I-01", status="valid")],
        pending_requests=[_make_request("I-01", "Q?", "A", "ctx")],
        target="verifier", gate_trigger="after", target_type="phase",
    )
    d = packet.to_dict()
    assert d["workflow"] == "refine"
    assert d["cycle"] == 2
    assert d["workflow_state"] == "paused_for_human"
    assert "gate" in d
    assert d["gate"]["target"] == "verifier"
    assert d["gate"]["gate_trigger"] == "after"
    assert d["gate"]["target_type"] == "phase"
    assert len(d["open_issues"]) == 1
    assert len(d["candidate_decisions"]) == 1


def test_review_packet_to_dict_is_json_serialisable():
    packet = build_review_packet(
        workflow="plan", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    dumped = json.dumps(packet.to_dict())
    loaded = json.loads(dumped)
    assert loaded["workflow"] == "plan"


# ---------------------------------------------------------------------------
# write_review_packet
# ---------------------------------------------------------------------------

def test_write_review_packet_creates_file(tmp_path):
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    out = tmp_path / REVIEW_PACKET_FILENAME
    write_review_packet(packet, out)
    assert out.exists()


def test_write_review_packet_valid_json(tmp_path):
    packet = build_review_packet(
        workflow="refine", cycle=1, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    out = tmp_path / REVIEW_PACKET_FILENAME
    write_review_packet(packet, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["workflow"] == "refine"
    assert "gate" in data


def test_write_review_packet_roundtrip(tmp_path):
    request = _make_request("I-42", "Should we include examples?", "Yes, in §3", "Draft §3")
    issue = _make_issue("I-42", status="deferred")
    packet = build_review_packet(
        workflow="refine", cycle=3, consecutive_clean_cycles=0,
        open_issues=[issue], pending_requests=[request],
    )
    out = tmp_path / REVIEW_PACKET_FILENAME
    write_review_packet(packet, out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert data["cycle"] == 3
    assert data["gate"]["sequence"] == 3
    assert data["open_issues"][0]["id"] == "I-42"
    assert data["candidate_decisions"][0]["suggested_answer"] == "Yes, in §3"


def test_write_review_packet_overwrites_existing(tmp_path):
    out = tmp_path / REVIEW_PACKET_FILENAME
    out.write_text("old content", encoding="utf-8")
    packet = build_review_packet(
        workflow="plan", cycle=2, consecutive_clean_cycles=0,
        open_issues=[], pending_requests=[],
    )
    write_review_packet(packet, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["workflow"] == "plan"


# ---------------------------------------------------------------------------
# REVIEW_PACKET_FILENAME constant
# ---------------------------------------------------------------------------

def test_review_packet_filename_constant():
    assert REVIEW_PACKET_FILENAME == "hitl_review_packet.json"
