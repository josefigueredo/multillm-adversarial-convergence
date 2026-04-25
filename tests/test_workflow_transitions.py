"""Unit tests for WorkflowTransitionEmitter — MM07 Step 2."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.audit_trail import NullAuditTrailWriter
from src.workflows.research_states import ResearchState
from src.workflows.refine_states import RefineState
from src.workflows.plan_states import PlanState
from src.workflows.transitions import WorkflowTransitionEmitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CapturingAudit:
    """In-memory audit writer that collects emitted events."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append({"event": event, **fields})

    @contextmanager
    def step(self, step: str, *, artifact_root=None, **fields):
        yield

    def transitions(self) -> list[dict]:
        return [e for e in self.events if e["event"] == "workflow_transition"]


# ---------------------------------------------------------------------------
# WorkflowTransitionEmitter
# ---------------------------------------------------------------------------

class TestWorkflowTransitionEmitter:

    def test_no_event_on_construction(self):
        audit = CapturingAudit()
        WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        assert audit.events == []

    def test_transition_emits_workflow_transition_event(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)
        assert len(audit.transitions()) == 1
        assert audit.transitions()[0]["event"] == "workflow_transition"

    def test_from_state_is_initial_state_value(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)
        assert audit.transitions()[0]["from_state"] == "idle"

    def test_to_state_is_string_not_enum(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)
        to = audit.transitions()[0]["to_state"]
        assert isinstance(to, str)
        assert to == "hypothesis"

    def test_workflow_field_is_set(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "refine", RefineState.IDLE)
        emitter.transition(RefineState.BUILDER)
        assert audit.transitions()[0]["workflow"] == "refine"

    def test_extra_fields_pass_through(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS, iteration=3, dimension="safety")
        evt = audit.transitions()[0]
        assert evt["iteration"] == 3
        assert evt["dimension"] == "safety"

    def test_current_state_updates_after_transition(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        assert emitter.current_state == ResearchState.IDLE
        emitter.transition(ResearchState.HYPOTHESIS)
        assert emitter.current_state == ResearchState.HYPOTHESIS

    def test_chained_transitions_use_previous_to_state_as_from_state(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)
        emitter.transition(ResearchState.EXECUTE)
        t = audit.transitions()
        assert t[0]["from_state"] == "idle"
        assert t[0]["to_state"] == "hypothesis"
        assert t[1]["from_state"] == "hypothesis"
        assert t[1]["to_state"] == "execute"

    def test_multiple_transitions_accumulate(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)
        emitter.transition(ResearchState.EXECUTE)
        emitter.transition(ResearchState.SCORE)
        assert len(audit.transitions()) == 3

    def test_works_with_null_audit_trail(self):
        emitter = WorkflowTransitionEmitter(NullAuditTrailWriter(), "research", ResearchState.IDLE)
        emitter.transition(ResearchState.HYPOTHESIS)  # must not raise
        assert emitter.current_state == ResearchState.HYPOTHESIS

    def test_works_with_refine_states(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "refine", RefineState.IDLE)
        emitter.transition(RefineState.BUILDER, cycle=1)
        emitter.transition(RefineState.CHALLENGER, cycle=1)
        t = audit.transitions()
        assert t[0]["to_state"] == "builder"
        assert t[1]["from_state"] == "builder"
        assert t[1]["to_state"] == "challenger"

    def test_works_with_plan_states(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "plan", PlanState.IDLE)
        emitter.transition(PlanState.BUILDER, cycle=1)
        assert audit.transitions()[0]["workflow"] == "plan"
        assert audit.transitions()[0]["to_state"] == "builder"

    def test_cross_cycle_from_arbitrator(self):
        """Simulates second run_cycle starting from ARBITRATOR state."""
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "refine", RefineState.ARBITRATOR)
        emitter.transition(RefineState.BUILDER, cycle=2)
        t = audit.transitions()[0]
        assert t["from_state"] == "arbitrator"
        assert t["to_state"] == "builder"

    def test_initial_state_preserved_without_transition(self):
        audit = CapturingAudit()
        emitter = WorkflowTransitionEmitter(audit, "refine", RefineState.IDLE)
        assert emitter.current_state == RefineState.IDLE
        assert audit.events == []
