"""Tests for workflow transition emission in the research loop."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.audit_trail import NullAuditTrailWriter
from src.research_loop import LoopContext, LoopState, run_iteration
from src.scorer import IterationScore
from src.workflows.research_states import ResearchState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CapturingAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append({"event": event, **fields})

    @contextmanager
    def step(self, step: str, *, artifact_root=None, **fields):
        yield

    def transitions(self) -> list[dict]:
        return [e for e in self.events if e["event"] == "workflow_transition"]


def _make_loop_ctx(audit_trail=None) -> LoopContext:
    noop = lambda *a, **kw: None
    config = MagicMock()
    config.execution.compress_every = 999  # prevent compression in tests
    return LoopContext(
        call_with=noop,
        invoke_for_strategy=noop,
        track_usage=noop,
        track_cost=noop,
        config=config,
        strategy=MagicMock(),
        track_candidate_usage=noop,
        collect_provenance=noop,
        methodology_summary=lambda: "",
        kb_summary=lambda: "",
        format_dimension_list=lambda l: ", ".join(l),
        goal_constraints_summary=lambda: "",
        audit_trail=audit_trail or NullAuditTrailWriter(),
        artifact_root=Path("."),
    )


_FAKE_HYPOTHESIS = {"dimension": "safety", "questions": ["Is it safe?"], "approach": "search"}
_SCORE_KEEP = IterationScore(coverage=80.0, quality=80.0, total=80.0)
_SCORE_DISCARD = IterationScore(coverage=10.0, quality=10.0, total=10.0)


# ---------------------------------------------------------------------------
# Happy-path transitions
# ---------------------------------------------------------------------------

class TestResearchIterationTransitions:

    def _run_with_patches(
        self,
        audit,
        *,
        hypothesis=_FAKE_HYPOTHESIS,
        findings="findings text",
        score=_SCORE_KEEP,
    ) -> LoopState:
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        with (
            patch("src.research_loop._generate_hypothesis", return_value=hypothesis),
            patch("src.research_loop._execute_research", return_value=findings),
            patch("src.research_loop._score", return_value=score),
            patch("src.research_loop._merge"),
            patch("src.research_loop._maybe_exhaust"),
            patch("src.research_loop._log_result"),
            patch("src.research_loop.write_iteration_markdown"),
        ):
            run_iteration(ctx, state)
        return state

    def test_successful_kept_iteration_emits_hypothesis_execute_score_decide_merge(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_KEEP)
        to_states = [t["to_state"] for t in audit.transitions()]
        for phase in ("hypothesis", "execute", "score", "decide", "merge"):
            assert phase in to_states, f"Missing transition to {phase}"

    def test_successful_discarded_iteration_does_not_emit_merge(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_DISCARD)
        to_states = [t["to_state"] for t in audit.transitions()]
        assert "merge" not in to_states

    def test_successful_discarded_iteration_emits_hypothesis_execute_score_decide(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_DISCARD)
        to_states = [t["to_state"] for t in audit.transitions()]
        for phase in ("hypothesis", "execute", "score", "decide"):
            assert phase in to_states, f"Missing transition to {phase}"

    def test_transitions_in_order_for_kept_iteration(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_KEEP)
        to_states = [t["to_state"] for t in audit.transitions()]
        expected = ["hypothesis", "execute", "score", "decide", "merge"]
        assert to_states == expected

    def test_workflow_field_is_research(self):
        audit = CapturingAudit()
        self._run_with_patches(audit)
        for t in audit.transitions():
            assert t["workflow"] == "research"

    def test_first_from_state_is_idle(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_KEEP)
        assert audit.transitions()[0]["from_state"] == "idle"

    def test_chained_from_states_are_correct(self):
        audit = CapturingAudit()
        self._run_with_patches(audit, score=_SCORE_KEEP)
        t = audit.transitions()
        assert t[0]["from_state"] == "idle"        and t[0]["to_state"] == "hypothesis"
        assert t[1]["from_state"] == "hypothesis"  and t[1]["to_state"] == "execute"
        assert t[2]["from_state"] == "execute"     and t[2]["to_state"] == "score"
        assert t[3]["from_state"] == "score"       and t[3]["to_state"] == "decide"
        assert t[4]["from_state"] == "decide"      and t[4]["to_state"] == "merge"

    def test_kept_iteration_persists_merge_state(self):
        audit = CapturingAudit()
        state = self._run_with_patches(audit, score=_SCORE_KEEP)
        assert state.current_workflow_state == ResearchState.MERGE

    def test_discarded_iteration_persists_decide_state(self):
        audit = CapturingAudit()
        state = self._run_with_patches(audit, score=_SCORE_DISCARD)
        assert state.current_workflow_state == ResearchState.DECIDE

    def test_second_iteration_starts_from_previous_end_state(self):
        """After a kept iteration (MERGE), the next should start from MERGE."""
        audit = CapturingAudit()
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        with (
            patch("src.research_loop._generate_hypothesis", return_value=_FAKE_HYPOTHESIS),
            patch("src.research_loop._execute_research", return_value="findings"),
            patch("src.research_loop._score", return_value=_SCORE_KEEP),
            patch("src.research_loop._merge"),
            patch("src.research_loop._maybe_exhaust"),
            patch("src.research_loop._log_result"),
            patch("src.research_loop.write_iteration_markdown"),
        ):
            run_iteration(ctx, state)
            audit.events.clear()
            run_iteration(ctx, state)
        first_t = audit.transitions()[0]
        assert first_t["from_state"] == "merge"
        assert first_t["to_state"] == "hypothesis"


# ---------------------------------------------------------------------------
# Abort paths — no state update, no spurious transitions
# ---------------------------------------------------------------------------

class TestResearchIterationAbortPaths:

    def test_hypothesis_failure_emits_no_transitions(self):
        audit = CapturingAudit()
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        with patch("src.research_loop._generate_hypothesis", return_value=None):
            run_iteration(ctx, state)
        assert audit.transitions() == []

    def test_hypothesis_failure_leaves_workflow_state_unchanged(self):
        audit = CapturingAudit()
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        state.current_workflow_state = ResearchState.MERGE  # simulate prior state
        with patch("src.research_loop._generate_hypothesis", return_value=None):
            run_iteration(ctx, state)
        assert state.current_workflow_state == ResearchState.MERGE

    def test_execute_failure_emits_hypothesis_but_not_execute(self):
        """Hypothesis succeeded, so HYPOTHESIS transition is emitted; execute failed, so EXECUTE is not."""
        audit = CapturingAudit()
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        with (
            patch("src.research_loop._generate_hypothesis", return_value=_FAKE_HYPOTHESIS),
            patch("src.research_loop._execute_research", return_value=""),
            patch("src.research_loop._maybe_exhaust"),
            patch("src.research_loop._log_result"),
        ):
            run_iteration(ctx, state)
        to_states = [t["to_state"] for t in audit.transitions()]
        assert "hypothesis" in to_states
        assert "execute" not in to_states

    def test_execute_failure_leaves_workflow_state_at_hypothesis(self):
        audit = CapturingAudit()
        ctx = _make_loop_ctx(audit_trail=audit)
        state = LoopState()
        with (
            patch("src.research_loop._generate_hypothesis", return_value=_FAKE_HYPOTHESIS),
            patch("src.research_loop._execute_research", return_value=""),
            patch("src.research_loop._maybe_exhaust"),
            patch("src.research_loop._log_result"),
        ):
            run_iteration(ctx, state)
        assert state.current_workflow_state == ResearchState.HYPOTHESIS
