"""Tests for MM08 Step 2 — HITL workflow gate definitions.

Covers:
- HitlGate dataclass shape and immutability
- GateTrigger / GateTarget enum values
- GATES_BY_MODE coverage per intervention mode
- get_gates_for_mode() lookup and error path
- get_gates() workflow-scoped view
- should_pause() convenience helper
"""

import pytest

from src.workflows.gates import (
    GATES_BY_MODE,
    VALID_WORKFLOWS,
    GateTarget,
    GateTrigger,
    HitlGate,
    get_gates,
    get_gates_for_mode,
    should_pause,
)
from src.config import VALID_INTERVENTION_MODES

# ---------------------------------------------------------------------------
# Active phases referenced in contracts.py
# ---------------------------------------------------------------------------

_RESEARCH_PHASES = frozenset({"hypothesis", "execute", "score", "decide", "merge"})
_CONVERGENCE_LOOP_PHASES = frozenset(
    {"builder", "challenger", "personas", "verifier", "arbitrator"}
)


# ===========================================================================
# HitlGate dataclass
# ===========================================================================


class TestHitlGate:
    def test_is_frozen(self):
        gate = HitlGate(
            workflow="research",
            target="hypothesis",
            target_type=GateTarget.PHASE,
            trigger=GateTrigger.BEFORE,
            description="test",
        )
        with pytest.raises((AttributeError, TypeError)):
            gate.target = "execute"  # type: ignore[misc]

    def test_is_hashable(self):
        gate = HitlGate(
            workflow="research",
            target="hypothesis",
            target_type=GateTarget.PHASE,
            trigger=GateTrigger.BEFORE,
            description="test",
        )
        s = frozenset({gate})
        assert gate in s

    def test_equality(self):
        a = HitlGate("research", "hypothesis", GateTarget.PHASE, GateTrigger.BEFORE, "x")
        b = HitlGate("research", "hypothesis", GateTarget.PHASE, GateTrigger.BEFORE, "x")
        assert a == b

    def test_inequality_on_workflow(self):
        a = HitlGate("research", "hypothesis", GateTarget.PHASE, GateTrigger.BEFORE, "x")
        b = HitlGate("refine", "hypothesis", GateTarget.PHASE, GateTrigger.BEFORE, "x")
        assert a != b


# ===========================================================================
# Enum values
# ===========================================================================


class TestEnumValues:
    def test_gate_trigger_values(self):
        assert GateTrigger.BEFORE == "before"
        assert GateTrigger.AFTER == "after"

    def test_gate_target_values(self):
        assert GateTarget.PHASE == "phase"
        assert GateTarget.CHECKPOINT == "checkpoint"


# ===========================================================================
# GATES_BY_MODE coverage
# ===========================================================================


class TestGatesByMode:
    def test_all_valid_modes_present(self):
        for mode in VALID_INTERVENTION_MODES:
            assert mode in GATES_BY_MODE, f"Missing mode: {mode}"

    def test_full_auto_has_no_gates(self):
        assert len(GATES_BY_MODE["full_auto"]) == 0

    # --- checkpoint_only ---------------------------------------------------

    def test_checkpoint_only_has_only_checkpoint_kind(self):
        for gate in GATES_BY_MODE["checkpoint_only"]:
            assert gate.target_type == GateTarget.CHECKPOINT

    def test_checkpoint_only_gates_are_all_after(self):
        for gate in GATES_BY_MODE["checkpoint_only"]:
            assert gate.trigger == GateTrigger.AFTER

    def test_checkpoint_only_includes_convergence(self):
        targets = {g.target for g in GATES_BY_MODE["checkpoint_only"]}
        assert "convergence" in targets

    def test_checkpoint_only_includes_run_complete(self):
        targets = {g.target for g in GATES_BY_MODE["checkpoint_only"]}
        assert "run_complete" in targets

    def test_checkpoint_only_gates_are_cross_cutting(self):
        for gate in GATES_BY_MODE["checkpoint_only"]:
            assert gate.workflow == "all"

    # --- decision_only -----------------------------------------------------

    def test_decision_only_has_only_phase_kind(self):
        for gate in GATES_BY_MODE["decision_only"]:
            assert gate.target_type == GateTarget.PHASE

    def test_decision_only_gates_are_all_after(self):
        for gate in GATES_BY_MODE["decision_only"]:
            assert gate.trigger == GateTrigger.AFTER

    def test_decision_only_includes_research_decide(self):
        gates = GATES_BY_MODE["decision_only"]
        assert any(g.workflow == "research" and g.target == "decide" for g in gates)

    def test_decision_only_includes_refine_verifier(self):
        gates = GATES_BY_MODE["decision_only"]
        assert any(g.workflow == "refine" and g.target == "verifier" for g in gates)

    def test_decision_only_includes_plan_verifier(self):
        gates = GATES_BY_MODE["decision_only"]
        assert any(g.workflow == "plan" and g.target == "verifier" for g in gates)

    # --- co_pilot ----------------------------------------------------------

    def test_co_pilot_has_only_before_phase_gates(self):
        for gate in GATES_BY_MODE["co_pilot"]:
            assert gate.trigger == GateTrigger.BEFORE
            assert gate.target_type == GateTarget.PHASE

    def test_co_pilot_covers_all_research_phases(self):
        research_targets = {
            g.target for g in GATES_BY_MODE["co_pilot"] if g.workflow == "research"
        }
        assert research_targets == _RESEARCH_PHASES

    def test_co_pilot_covers_all_refine_phases(self):
        refine_targets = {
            g.target for g in GATES_BY_MODE["co_pilot"] if g.workflow == "refine"
        }
        assert refine_targets == _CONVERGENCE_LOOP_PHASES

    def test_co_pilot_covers_all_plan_phases(self):
        plan_targets = {
            g.target for g in GATES_BY_MODE["co_pilot"] if g.workflow == "plan"
        }
        assert plan_targets == _CONVERGENCE_LOOP_PHASES

    # --- step_review -------------------------------------------------------

    def test_step_review_phase_gates_are_all_after(self):
        phase_gates = {
            g for g in GATES_BY_MODE["step_review"] if g.target_type == GateTarget.PHASE
        }
        for gate in phase_gates:
            assert gate.trigger == GateTrigger.AFTER

    def test_step_review_covers_all_research_phases(self):
        research_targets = {
            g.target
            for g in GATES_BY_MODE["step_review"]
            if g.workflow == "research" and g.target_type == GateTarget.PHASE
        }
        assert research_targets == _RESEARCH_PHASES

    def test_step_review_covers_all_refine_phases(self):
        refine_targets = {
            g.target
            for g in GATES_BY_MODE["step_review"]
            if g.workflow == "refine" and g.target_type == GateTarget.PHASE
        }
        assert refine_targets == _CONVERGENCE_LOOP_PHASES

    def test_step_review_covers_all_plan_phases(self):
        plan_targets = {
            g.target
            for g in GATES_BY_MODE["step_review"]
            if g.workflow == "plan" and g.target_type == GateTarget.PHASE
        }
        assert plan_targets == _CONVERGENCE_LOOP_PHASES

    def test_step_review_includes_convergence_checkpoint(self):
        checkpoint_targets = {
            g.target
            for g in GATES_BY_MODE["step_review"]
            if g.target_type == GateTarget.CHECKPOINT
        }
        assert "convergence" in checkpoint_targets


# ===========================================================================
# get_gates_for_mode()
# ===========================================================================


class TestGetGatesForMode:
    def test_returns_frozenset(self):
        result = get_gates_for_mode("full_auto")
        assert isinstance(result, frozenset)

    def test_raises_on_unknown_mode(self):
        with pytest.raises(ValueError, match="intervention mode"):
            get_gates_for_mode("turbo_mode")

    def test_returns_same_object_as_dict(self):
        assert get_gates_for_mode("checkpoint_only") is GATES_BY_MODE["checkpoint_only"]


# ===========================================================================
# get_gates() — workflow-scoped view
# ===========================================================================


class TestGetGates:
    def test_research_co_pilot_excludes_refine_gates(self):
        gates = get_gates("co_pilot", "research")
        assert all(g.workflow in ("research", "all") for g in gates)

    def test_refine_co_pilot_excludes_research_gates(self):
        gates = get_gates("co_pilot", "refine")
        assert all(g.workflow in ("refine", "all") for g in gates)

    def test_cross_cutting_gates_appear_in_every_workflow(self):
        for wf in ("research", "refine", "plan"):
            gates = get_gates("checkpoint_only", wf)
            assert len(gates) == len(GATES_BY_MODE["checkpoint_only"])

    def test_full_auto_empty_for_any_workflow(self):
        for wf in ("research", "refine", "plan"):
            assert len(get_gates("full_auto", wf)) == 0

    def test_raises_on_unknown_mode(self):
        with pytest.raises(ValueError, match="intervention mode"):
            get_gates("bad_mode", "research")

    def test_raises_on_unknown_workflow(self):
        with pytest.raises(ValueError, match="workflow"):
            get_gates("co_pilot", "doc")

    def test_raises_on_typo_workflow(self):
        with pytest.raises(ValueError, match="workflow"):
            get_gates("co_pilot", "reseach")

    def test_valid_workflows_accepted(self):
        for wf in VALID_WORKFLOWS:
            get_gates("full_auto", wf)  # should not raise


# ===========================================================================
# should_pause()
# ===========================================================================


class TestShouldPause:
    def test_full_auto_never_pauses(self):
        for phase in ("hypothesis", "verifier", "convergence"):
            for trigger in (GateTrigger.BEFORE, GateTrigger.AFTER):
                assert not should_pause("full_auto", "research", phase, trigger)

    def test_checkpoint_only_pauses_at_convergence(self):
        assert should_pause("checkpoint_only", "research", "convergence", GateTrigger.AFTER)
        assert should_pause("checkpoint_only", "refine", "convergence", GateTrigger.AFTER)
        assert should_pause("checkpoint_only", "plan", "convergence", GateTrigger.AFTER)

    def test_checkpoint_only_does_not_pause_before_convergence(self):
        assert not should_pause("checkpoint_only", "research", "convergence", GateTrigger.BEFORE)

    def test_checkpoint_only_pauses_at_run_complete(self):
        assert should_pause("checkpoint_only", "research", "run_complete", GateTrigger.AFTER)

    def test_checkpoint_only_does_not_pause_at_phases(self):
        assert not should_pause("checkpoint_only", "research", "hypothesis", GateTrigger.AFTER)

    def test_decision_only_pauses_research_decide_after(self):
        assert should_pause("decision_only", "research", "decide", GateTrigger.AFTER)

    def test_decision_only_does_not_pause_before_decide(self):
        assert not should_pause("decision_only", "research", "decide", GateTrigger.BEFORE)

    def test_decision_only_pauses_refine_verifier_after(self):
        assert should_pause("decision_only", "refine", "verifier", GateTrigger.AFTER)

    def test_decision_only_does_not_pause_research_verifier(self):
        # "verifier" is a refine/plan phase — not a research phase
        assert not should_pause("decision_only", "research", "verifier", GateTrigger.AFTER)

    def test_co_pilot_pauses_before_hypothesis(self):
        assert should_pause("co_pilot", "research", "hypothesis", GateTrigger.BEFORE)

    def test_co_pilot_does_not_pause_after_hypothesis(self):
        assert not should_pause("co_pilot", "research", "hypothesis", GateTrigger.AFTER)

    def test_co_pilot_pauses_before_all_research_phases(self):
        for phase in _RESEARCH_PHASES:
            assert should_pause("co_pilot", "research", phase, GateTrigger.BEFORE), phase

    def test_co_pilot_pauses_before_all_refine_phases(self):
        for phase in _CONVERGENCE_LOOP_PHASES:
            assert should_pause("co_pilot", "refine", phase, GateTrigger.BEFORE), phase

    def test_step_review_pauses_after_hypothesis(self):
        assert should_pause("step_review", "research", "hypothesis", GateTrigger.AFTER)

    def test_step_review_does_not_pause_before_hypothesis(self):
        assert not should_pause("step_review", "research", "hypothesis", GateTrigger.BEFORE)

    def test_step_review_pauses_after_all_research_phases(self):
        for phase in _RESEARCH_PHASES:
            assert should_pause("step_review", "research", phase, GateTrigger.AFTER), phase

    def test_step_review_pauses_after_all_refine_phases(self):
        for phase in _CONVERGENCE_LOOP_PHASES:
            assert should_pause("step_review", "refine", phase, GateTrigger.AFTER), phase

    def test_step_review_pauses_after_convergence(self):
        assert should_pause("step_review", "refine", "convergence", GateTrigger.AFTER)
        assert should_pause("step_review", "plan", "convergence", GateTrigger.AFTER)

    def test_invalid_trigger_raises(self):
        with pytest.raises(ValueError):
            should_pause("checkpoint_only", "research", "convergence", "sideways")  # type: ignore[arg-type]

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="intervention mode"):
            should_pause("invalid_mode", "research", "hypothesis", GateTrigger.BEFORE)

    def test_unknown_workflow_raises(self):
        with pytest.raises(ValueError, match="workflow"):
            should_pause("co_pilot", "plans", "builder", GateTrigger.BEFORE)

    def test_workflow_typo_raises(self):
        with pytest.raises(ValueError, match="workflow"):
            should_pause("co_pilot", "reseach", "hypothesis", GateTrigger.BEFORE)
