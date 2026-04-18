from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backends.types import AgentResponse
from src.config import BackendsConfig, PlanConfig
from src.document_loop import Issue
from src.hitl import DeferReason, HumanDecision
from src.plan_loop import (
    PlanCycleContext,
    PlanCycleState,
    _plan_should_stop,
    _update_plan_convergence,
    run_plan_cycle,
)


def _make_config(**kwargs) -> PlanConfig:
    defaults = dict(topic="T", goal="G", convergence_cycles=2, max_cycles=10)
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_invoke(text: str = "[]"):
    def invoke(prompt, backend_obj, backend_name):
        return AgentResponse(text=text, cost_usd=0.0, is_error=False,
                             input_tokens=0, output_tokens=0)
    return invoke


def _make_ctx(config=None) -> PlanCycleContext:
    cfg = config or _make_config()
    return PlanCycleContext(
        call_with=_make_invoke(),
        invoke_for_strategy=_make_invoke(),
        track_usage=lambda resp, name: None,
        track_cost=lambda cost, name: None,
        config=cfg,
        human_decisions=[],
        update_issue_registry=lambda issues: None,
    )


# ── _plan_should_stop ────────────────────────────────────────────────────────

def test_should_stop_when_convergence_cycles_reached():
    cfg = _make_config(convergence_cycles=2, max_cycles=0)
    state = PlanCycleState()
    state.consecutive_clean_cycles = 2
    assert _plan_should_stop(state, cfg) is True


def test_should_not_stop_below_convergence_cycles():
    cfg = _make_config(convergence_cycles=2, max_cycles=0)
    state = PlanCycleState()
    state.consecutive_clean_cycles = 1
    assert _plan_should_stop(state, cfg) is False


def test_should_stop_at_max_cycles():
    cfg = _make_config(convergence_cycles=5, max_cycles=3)
    state = PlanCycleState()
    state.cycle = 3
    assert _plan_should_stop(state, cfg) is True


def test_max_cycles_zero_means_no_cap():
    cfg = _make_config(convergence_cycles=99, max_cycles=0)
    state = PlanCycleState()
    state.cycle = 1000
    assert _plan_should_stop(state, cfg) is False


# ── _update_plan_convergence ─────────────────────────────────────────────────

def test_clean_cycle_increments_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 1
    _update_plan_convergence(state, valid_count=0, human_required_count=0)
    assert state.consecutive_clean_cycles == 2


def test_valid_critiques_resets_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 3
    _update_plan_convergence(state, valid_count=1, human_required_count=0)
    assert state.consecutive_clean_cycles == 0


def test_human_required_resets_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 2
    _update_plan_convergence(state, valid_count=0, human_required_count=1)
    assert state.consecutive_clean_cycles == 0


# ── run_plan_cycle ───────────────────────────────────────────────────────────

def test_run_plan_cycle_increments_cycle():
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# Revised Plan"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_plan_cycle(state, ctx, strategy)

    assert state.cycle == 1


def test_run_plan_cycle_returns_counts():
    from src.document_strategy import VerifiedCritique
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)

    valid = VerifiedCritique(description="d", section_ref="§1",
                              raised_by="challenger", status="valid")
    stale = VerifiedCritique(description="d", section_ref="§2",
                              raised_by="architect", status="stale")
    deferred = VerifiedCritique(description="d", section_ref="§3",
                                 raised_by="qa_engineer", status="deferred",
                                 defer_reason="out_of_scope")

    strategy = MagicMock()
    strategy.run_builder.return_value = "# Plan v2"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = [valid, stale, deferred]
    strategy.run_arbitrator.return_value = []

    v, s, d = run_plan_cycle(state, ctx, strategy)

    assert v == 1
    assert s == 1
    assert d == 1


def test_run_plan_cycle_updates_plan_text():
    cfg = _make_config()
    state = PlanCycleState(plan="# Old")
    ctx = _make_ctx(cfg)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# New"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_plan_cycle(state, ctx, strategy)

    assert state.plan == "# New"
    assert state.plan_versions == ["# New"]
