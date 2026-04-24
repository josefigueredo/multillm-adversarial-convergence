from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audit_trail import AuditTrailWriter, NullAuditTrailWriter
from src.config import DocumentConfig
from src.document_loop import (
    CycleContext,
    CycleState,
    Issue,
    _should_stop,
    _update_convergence,
    run_cycle,
)
from src.hitl import DeferReason, HumanDecision, HumanInputRequest


def _make_config(**kwargs) -> DocumentConfig:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(kwargs)
    return DocumentConfig(**defaults)


def _make_ctx(config=None, *, artifact_root: Path | None = None, audit_trail=None) -> CycleContext:
    noop = lambda *a, **kw: None
    return CycleContext(
        call_with=noop,
        invoke_for_strategy=noop,
        track_usage=noop,
        track_cost=noop,
        config=config or _make_config(),
        human_decisions=[],
        read_prd_section=lambda s: "",
        update_issue_registry=noop,
        audit_trail=audit_trail or NullAuditTrailWriter(),
        artifact_root=artifact_root or Path("."),
    )


# ── Issue ───────────────────────────────────────────────────────────────────

def test_issue_defaults():
    i = Issue(id="I-01", description="desc", raised_by="challenger",
               cycle=1, section_ref="§3", status="open")
    assert i.defer_reason is None
    assert i.verified_cycle is None
    assert i.patch_applied is False


# ── CycleState ──────────────────────────────────────────────────────────────

def test_cycle_state_defaults():
    s = CycleState()
    assert s.prd == ""
    assert s.cycle == 0
    assert s.consecutive_clean_cycles == 0
    assert s.prd_path == Path("PRD.md")


def test_cycle_state_prd_path_override():
    s = CycleState(prd_path=Path("SPEC.md"))
    assert s.prd_path == Path("SPEC.md")


# ── Convergence logic ────────────────────────────────────────────────────────

def test_should_stop_false_when_no_clean_cycles():
    cfg = _make_config(convergence_cycles=1)
    s = CycleState(consecutive_clean_cycles=0, cycle=1)
    assert _should_stop(s, cfg) is False


def test_should_stop_true_when_clean_cycles_reached():
    cfg = _make_config(convergence_cycles=1)
    s = CycleState(consecutive_clean_cycles=1, cycle=2)
    assert _should_stop(s, cfg) is True


def test_should_stop_true_when_max_cycles_reached():
    cfg = _make_config(max_cycles=3, convergence_cycles=99)
    s = CycleState(cycle=3)
    assert _should_stop(s, cfg) is True


def test_should_stop_false_when_below_max_cycles():
    cfg = _make_config(max_cycles=5, convergence_cycles=99)
    s = CycleState(cycle=2)
    assert _should_stop(s, cfg) is False


def test_update_convergence_increments_when_clean():
    s = CycleState(consecutive_clean_cycles=0)
    _update_convergence(s, valid_count=0, human_required_count=0)
    assert s.consecutive_clean_cycles == 1


def test_update_convergence_resets_when_valid():
    s = CycleState(consecutive_clean_cycles=3)
    _update_convergence(s, valid_count=2, human_required_count=0)
    assert s.consecutive_clean_cycles == 0


def test_update_convergence_resets_when_human_required():
    s = CycleState(consecutive_clean_cycles=2)
    _update_convergence(s, valid_count=0, human_required_count=1)
    assert s.consecutive_clean_cycles == 0


def test_update_convergence_stale_does_not_reset():
    s = CycleState(consecutive_clean_cycles=1)
    _update_convergence(s, valid_count=0, human_required_count=0)
    assert s.consecutive_clean_cycles == 2


# ── CycleContext ─────────────────────────────────────────────────────────────

def test_cycle_context_is_base_context_subclass():
    from src.run_state import BaseContext
    assert issubclass(CycleContext, BaseContext)


def test_cycle_context_construction():
    ctx = _make_ctx()
    assert ctx.human_decisions == []
    assert ctx.config.topic == "T"


# ── run_cycle ────────────────────────────────────────────────────────────────

def _make_strategy_mock(
    builder_text="PRD v2",
    verified=None,
    patches=None,
) -> MagicMock:
    from src.document_strategy import VerifiedCritique
    s = MagicMock()
    s.run_builder.return_value = builder_text
    s.run_challenger.return_value = []
    s.run_personas.return_value = []
    s.run_verifier.return_value = verified if verified is not None else []
    s.run_arbitrator.return_value = patches if patches is not None else []
    return s


def test_run_cycle_increments_cycle():
    state = CycleState()
    run_cycle(state, _make_ctx(), _make_strategy_mock(), interactive=False)
    assert state.cycle == 1


def test_run_cycle_updates_prd():
    state = CycleState(prd="old prd")
    run_cycle(state, _make_ctx(), _make_strategy_mock(builder_text="new prd"), interactive=False)
    assert state.prd == "new prd"


def test_run_cycle_appends_prd_version():
    state = CycleState(prd="old")
    run_cycle(state, _make_ctx(), _make_strategy_mock(builder_text="new"), interactive=False)
    assert "new" in state.prd_versions


def test_run_cycle_clean_increments_consecutive():
    state = CycleState()
    run_cycle(state, _make_ctx(), _make_strategy_mock(), interactive=False)
    assert state.consecutive_clean_cycles == 1


def test_run_cycle_valid_critiques_reset_consecutive():
    from src.document_strategy import VerifiedCritique
    state = CycleState(consecutive_clean_cycles=2)
    verified = [VerifiedCritique(description="d", section_ref="§1",
                                  raised_by="challenger", status="valid")]
    run_cycle(state, _make_ctx(), _make_strategy_mock(verified=verified), interactive=False)
    assert state.consecutive_clean_cycles == 0


def test_run_cycle_human_required_noninteractive_leaves_pending():
    from src.document_strategy import VerifiedCritique
    state = CycleState()
    verified = [VerifiedCritique(
        description="d", section_ref="§5", raised_by="architect",
        status="deferred", defer_reason=DeferReason.HUMAN_REQUIRED,
        question="Q?", suggested_answer="A",
    )]
    run_cycle(state, _make_ctx(), _make_strategy_mock(verified=verified), interactive=False)
    assert len(state.pending_human_inputs) == 1
    assert state.consecutive_clean_cycles == 0


def test_run_cycle_returns_counts():
    from src.document_strategy import VerifiedCritique
    valid = [VerifiedCritique(description="d", section_ref="§1",
                               raised_by="challenger", status="valid")]
    stale = [VerifiedCritique(description="s", section_ref="§2",
                               raised_by="challenger", status="stale")]
    state = CycleState()
    v_count, s_count, d_count = run_cycle(
        state, _make_ctx(), _make_strategy_mock(verified=valid + stale), interactive=False
    )
    assert v_count == 1
    assert s_count == 1
    assert d_count == 0


def test_run_cycle_adds_issues_to_registry():
    from src.document_strategy import VerifiedCritique
    verified = [VerifiedCritique(description="d", section_ref="§1",
                                  raised_by="challenger", status="valid")]
    state = CycleState()
    run_cycle(state, _make_ctx(), _make_strategy_mock(verified=verified), interactive=False)
    assert len(state.issue_registry) == 1
    assert state.issue_registry[0].status == "valid"
    assert state.issue_registry[0].id == "I-01"


def test_run_cycle_emits_progress_logs(caplog):
    state = CycleState()
    strategy = _make_strategy_mock()

    with caplog.at_level("INFO", logger="autoresearch"):
        run_cycle(state, _make_ctx(), strategy, interactive=False)

    text = caplog.text
    assert "[refine][cycle 001] builder starting" in text
    assert "[refine][cycle 001] challenger completed (0 critique(s))" in text
    assert "[refine][cycle 001] personas starting" in text
    assert "[refine][cycle 001] verifier completed (0 classified critique(s))" in text
    assert "[refine][cycle 001] arbitrator completed (0 patch(es))" in text
    assert "[refine][cycle 001] cycle complete (valid=0 stale=0 deferred=0 clean_streak=1)" in text


def test_run_cycle_writes_audit_trail_events(tmp_path: Path):
    state = CycleState()
    strategy = _make_strategy_mock()
    audit_trail = AuditTrailWriter(tmp_path / "audit_trail.jsonl", mode="refine", run_id="refine-test")

    run_cycle(
        state,
        _make_ctx(artifact_root=tmp_path, audit_trail=audit_trail),
        strategy,
        interactive=False,
    )

    content = (tmp_path / "audit_trail.jsonl").read_text(encoding="utf-8")
    assert '"event": "step_started"' in content
    assert '"step": "builder"' in content
    assert '"step": "verifier"' in content
    assert '"event": "step_completed"' in content
