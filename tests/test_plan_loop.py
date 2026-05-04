from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from src.backends.types import AgentResponse
from src.audit_trail import AuditTrailWriter, NullAuditTrailWriter
from src.config import BackendsConfig, PlanConfig
from src.implement.document_loop import Issue
from src.policy.hitl import DeferReason, HumanDecision
from src.implement.plan_loop import (
    PlanCycleContext,
    PlanCycleState,
    _plan_should_stop,
    _update_plan_convergence,
    run_plan_cycle,
)
from src.workflows.plan_states import PlanState


def _make_config(**kwargs) -> PlanConfig:
    defaults = dict(topic="T", goal="G", convergence_cycles=2, max_cycles=10)
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_invoke(text: str = "[]"):
    def invoke(prompt, backend_obj, backend_name):
        return AgentResponse(text=text, cost_usd=0.0, is_error=False,
                             input_tokens=0, output_tokens=0)
    return invoke


def _make_ctx(config=None, *, artifact_root: Path | None = None, audit_trail=None) -> PlanCycleContext:
    cfg = config or _make_config()
    return PlanCycleContext(
        call_with=_make_invoke(),
        invoke_for_strategy=_make_invoke(),
        track_usage=lambda resp, name: None,
        track_cost=lambda cost, name: None,
        config=cfg,
        human_decisions=[],
        update_issue_registry=lambda issues: None,
        audit_trail=audit_trail or NullAuditTrailWriter(),
        artifact_root=artifact_root or Path("."),
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
    from src.implement.document_strategy import VerifiedCritique
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


def test_run_plan_cycle_collects_human_decisions_interactively():
    from src.implement.document_strategy import VerifiedCritique
    from unittest.mock import patch

    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)

    deferred_human = VerifiedCritique(
        description="needs human",
        section_ref="Task 1",
        raised_by="qa_engineer",
        status="deferred",
        defer_reason=DeferReason.HUMAN_REQUIRED,
        question="Should we add rollback?",
        suggested_answer="Yes",
    )

    strategy = MagicMock()
    strategy.run_builder.return_value = "# Plan v2"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = [deferred_human]
    strategy.run_arbitrator.return_value = []

    fake_decision = HumanDecision(
        issue_id="I-001",
        question="Should we add rollback?",
        answer="Yes",
        answered_at="2026-04-18T00:00:00+00:00",
        answered_by="human",
    )

    with patch("src.policy.hitl.collect_interactive", return_value=[fake_decision]):
        run_plan_cycle(state, ctx, strategy, interactive=True)

    assert len(state.human_decisions) == 1
    assert state.human_decisions[0].answer == "Yes"
    assert len(state.pending_human_inputs) == 0  # cleared after collection


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


def test_run_plan_cycle_emits_progress_logs(caplog):
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# Revised Plan"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    with caplog.at_level("INFO", logger="autoresearch"):
        run_plan_cycle(state, ctx, strategy, interactive=False)

    text = caplog.text
    assert "[plan][cycle 001] builder starting" in text
    assert "[plan][cycle 001] challenger completed (0 critique(s))" in text
    assert "[plan][cycle 001] personas starting" in text
    assert "[plan][cycle 001] verifier completed (0 classified critique(s))" in text
    assert "[plan][cycle 001] arbitrator completed (0 patch(es))" in text
    assert "[plan][cycle 001] cycle complete (valid=0 stale=0 deferred=0 clean_streak=1)" in text


def test_run_plan_cycle_writes_audit_trail_events(tmp_path: Path):
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    audit_trail = AuditTrailWriter(tmp_path / "audit_trail.jsonl", mode="plan", run_id="plan-test")
    ctx = _make_ctx(cfg, artifact_root=tmp_path, audit_trail=audit_trail)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# Revised Plan"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_plan_cycle(state, ctx, strategy, interactive=False)

    content = (tmp_path / "audit_trail.jsonl").read_text(encoding="utf-8")
    assert '"step": "builder"' in content
    assert '"step": "personas"' in content
    assert '"event": "step_completed"' in content


# ── Workflow transition emission ─────────────────────────────────────────────

class CapturingAudit:
    """In-memory audit writer for transition tests."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append({"event": event, **fields})

    @contextmanager
    def step(self, step: str, *, artifact_root=None, **fields):
        self.emit("step_started", step=step, **fields)
        yield
        self.emit("step_completed", step=step, **fields)

    def transitions(self) -> list[dict]:
        return [e for e in self.events if e["event"] == "workflow_transition"]


def _make_clean_strategy() -> MagicMock:
    strategy = MagicMock()
    strategy.run_builder.return_value = "# Plan"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []
    return strategy


class TestPlanWorkflowTransitionEmission:

    def _make_capturing_ctx(self):
        audit = CapturingAudit()
        ctx = _make_ctx(audit_trail=audit)
        return ctx, audit

    def test_run_plan_cycle_emits_all_five_phase_transitions(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        to_states = [t["to_state"] for t in audit.transitions()]
        for phase in ("builder", "challenger", "personas", "verifier", "arbitrator"):
            assert phase in to_states, f"Missing transition to {phase}"

    def test_run_plan_cycle_transitions_in_order(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        to_states = [t["to_state"] for t in audit.transitions()]
        expected_order = ["builder", "challenger", "personas", "verifier", "arbitrator"]
        indices = [to_states.index(p) for p in expected_order]
        assert indices == sorted(indices)

    def test_run_plan_cycle_workflow_field_is_plan(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        for t in audit.transitions():
            assert t["workflow"] == "plan"

    def test_run_plan_cycle_first_from_state_is_idle(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        assert audit.transitions()[0]["from_state"] == "idle"

    def test_run_plan_cycle_persists_workflow_state_as_arbitrator(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        assert state.current_workflow_state == PlanState.ARBITRATOR

    def test_run_plan_cycle_second_call_transitions_from_arbitrator(self):
        ctx, audit = self._make_capturing_ctx()
        state = PlanCycleState()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        audit.events.clear()
        run_plan_cycle(state, ctx, _make_clean_strategy(), interactive=False)
        first = audit.transitions()[0]
        assert first["from_state"] == "arbitrator"
        assert first["to_state"] == "builder"
