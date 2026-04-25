"""Tests for workflow state machine models — MM07 Step 1."""

from __future__ import annotations

import pytest

from src.workflows.research_states import (
    ResearchState,
    TERMINAL_STATES as R_TERMINAL,
    PAUSE_STATES as R_PAUSE,
    RESUME_STATES as R_RESUME,
    TRANSITIONS as R_TRANSITIONS,
)
from src.workflows.refine_states import (
    RefineState,
    TERMINAL_STATES as REF_TERMINAL,
    PAUSE_STATES as REF_PAUSE,
    RESUME_STATES as REF_RESUME,
    TRANSITIONS as REF_TRANSITIONS,
)
from src.workflows.plan_states import (
    PlanState,
    TERMINAL_STATES as PLAN_TERMINAL,
    PAUSE_STATES as PLAN_PAUSE,
    RESUME_STATES as PLAN_RESUME,
    TRANSITIONS as PLAN_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _all_targets(transitions: dict) -> frozenset:
    result: set = set()
    for nexts in transitions.values():
        result |= nexts
    return frozenset(result)


# ---------------------------------------------------------------------------
# ResearchState
# ---------------------------------------------------------------------------

class TestResearchStateMembership:
    def test_idle(self):
        assert ResearchState.IDLE in ResearchState

    def test_hypothesis(self):
        assert ResearchState.HYPOTHESIS in ResearchState

    def test_execute(self):
        assert ResearchState.EXECUTE in ResearchState

    def test_score(self):
        assert ResearchState.SCORE in ResearchState

    def test_decide(self):
        assert ResearchState.DECIDE in ResearchState

    def test_merge(self):
        assert ResearchState.MERGE in ResearchState

    def test_converged(self):
        assert ResearchState.CONVERGED in ResearchState

    def test_interrupted(self):
        assert ResearchState.INTERRUPTED in ResearchState

    def test_str_values_are_lowercase(self):
        for state in ResearchState:
            assert state.value == state.value.lower()

    def test_state_is_str(self):
        """ResearchState members must be usable as plain strings (str mixin)."""
        assert isinstance(ResearchState.IDLE.value, str)


class TestResearchTerminalStates:
    def test_terminal_states_are_subset_of_all(self):
        assert R_TERMINAL <= frozenset(ResearchState)

    def test_converged_is_terminal(self):
        assert ResearchState.CONVERGED in R_TERMINAL

    def test_interrupted_is_terminal(self):
        assert ResearchState.INTERRUPTED in R_TERMINAL

    def test_idle_is_not_terminal(self):
        assert ResearchState.IDLE not in R_TERMINAL

    def test_hypothesis_is_not_terminal(self):
        assert ResearchState.HYPOTHESIS not in R_TERMINAL


class TestResearchPauseResume:
    def test_no_pause_states(self):
        """Research loop has no human-gate pause; pause set must be empty."""
        assert R_PAUSE == frozenset()

    def test_no_resume_states(self):
        assert R_RESUME == frozenset()


class TestResearchTransitions:
    def test_transitions_cover_all_states(self):
        assert set(R_TRANSITIONS.keys()) == set(ResearchState)

    def test_all_transition_targets_are_valid(self):
        all_states = frozenset(ResearchState)
        for state, nexts in R_TRANSITIONS.items():
            assert nexts <= all_states, f"Invalid targets from {state}: {nexts - all_states}"

    def test_terminal_states_have_no_transitions(self):
        for state in R_TERMINAL:
            assert R_TRANSITIONS[state] == frozenset(), f"{state} must have no transitions"

    def test_nonterminal_states_have_at_least_one_transition(self):
        nonterminal = frozenset(ResearchState) - R_TERMINAL
        for state in nonterminal:
            assert R_TRANSITIONS[state], f"{state} has no transitions"

    def test_idle_leads_to_hypothesis(self):
        assert ResearchState.HYPOTHESIS in R_TRANSITIONS[ResearchState.IDLE]

    def test_hypothesis_can_converge(self):
        """HYPOTHESIS → CONVERGED when no dimensions remain."""
        assert ResearchState.CONVERGED in R_TRANSITIONS[ResearchState.HYPOTHESIS]

    def test_interrupted_reachable_from_all_active_phases(self):
        """Every active research phase can transition to INTERRUPTED on failure.

        Active phases are all states that invoke live backend/scoring work —
        i.e. every non-terminal, non-idle phase.
        """
        active_phases = (
            ResearchState.HYPOTHESIS,
            ResearchState.EXECUTE,
            ResearchState.SCORE,
            ResearchState.DECIDE,
            ResearchState.MERGE,
        )
        for state in active_phases:
            assert ResearchState.INTERRUPTED in R_TRANSITIONS[state], (
                f"{state} must be able to transition to INTERRUPTED"
            )

    def test_execute_can_be_interrupted(self):
        assert ResearchState.INTERRUPTED in R_TRANSITIONS[ResearchState.EXECUTE]

    def test_decide_branches_keep_or_discard(self):
        """DECIDE → MERGE (keep) or HYPOTHESIS (discard)."""
        assert ResearchState.MERGE in R_TRANSITIONS[ResearchState.DECIDE]
        assert ResearchState.HYPOTHESIS in R_TRANSITIONS[ResearchState.DECIDE]

    def test_all_states_reachable(self):
        """Every state except IDLE must appear as a transition target."""
        targets = _all_targets(R_TRANSITIONS)
        for state in ResearchState:
            if state == ResearchState.IDLE:
                continue
            assert state in targets, f"{state} is unreachable"


# ---------------------------------------------------------------------------
# RefineState
# ---------------------------------------------------------------------------

class TestRefineStateMembership:
    def test_idle(self):
        assert RefineState.IDLE in RefineState

    def test_builder(self):
        assert RefineState.BUILDER in RefineState

    def test_challenger(self):
        assert RefineState.CHALLENGER in RefineState

    def test_personas(self):
        assert RefineState.PERSONAS in RefineState

    def test_verifier(self):
        assert RefineState.VERIFIER in RefineState

    def test_paused_for_human(self):
        assert RefineState.PAUSED_FOR_HUMAN in RefineState

    def test_arbitrator(self):
        assert RefineState.ARBITRATOR in RefineState

    def test_converged(self):
        assert RefineState.CONVERGED in RefineState

    def test_interrupted(self):
        assert RefineState.INTERRUPTED in RefineState

    def test_str_values_are_lowercase(self):
        for state in RefineState:
            assert state.value == state.value.lower()


class TestRefineTerminalStates:
    def test_terminal_states_are_subset(self):
        assert REF_TERMINAL <= frozenset(RefineState)

    def test_converged_is_terminal(self):
        assert RefineState.CONVERGED in REF_TERMINAL

    def test_interrupted_is_terminal(self):
        assert RefineState.INTERRUPTED in REF_TERMINAL

    def test_idle_not_terminal(self):
        assert RefineState.IDLE not in REF_TERMINAL

    def test_paused_for_human_not_terminal(self):
        assert RefineState.PAUSED_FOR_HUMAN not in REF_TERMINAL


class TestRefinePauseResume:
    def test_paused_for_human_is_pause_state(self):
        assert RefineState.PAUSED_FOR_HUMAN in REF_PAUSE

    def test_pause_states_are_subset(self):
        assert REF_PAUSE <= frozenset(RefineState)

    def test_resume_states_are_subset(self):
        assert REF_RESUME <= frozenset(RefineState)

    def test_pause_transitions_are_resume_states(self):
        """Transitions from every pause state must equal the resume set."""
        for pause_state in REF_PAUSE:
            assert REF_TRANSITIONS[pause_state] == REF_RESUME, (
                f"Transitions from {pause_state} must equal RESUME_STATES"
            )

    def test_arbitrator_is_resume_target(self):
        """After human input, workflow resumes at ARBITRATOR."""
        assert RefineState.ARBITRATOR in REF_RESUME


class TestRefineTransitions:
    def test_transitions_cover_all_states(self):
        assert set(REF_TRANSITIONS.keys()) == set(RefineState)

    def test_all_transition_targets_are_valid(self):
        all_states = frozenset(RefineState)
        for state, nexts in REF_TRANSITIONS.items():
            assert nexts <= all_states, f"Invalid targets from {state}: {nexts - all_states}"

    def test_terminal_states_have_no_transitions(self):
        for state in REF_TERMINAL:
            assert REF_TRANSITIONS[state] == frozenset()

    def test_nonterminal_states_have_at_least_one_transition(self):
        nonterminal = frozenset(RefineState) - REF_TERMINAL
        for state in nonterminal:
            assert REF_TRANSITIONS[state], f"{state} has no transitions"

    def test_idle_leads_to_builder(self):
        assert RefineState.BUILDER in REF_TRANSITIONS[RefineState.IDLE]

    def test_verifier_can_pause(self):
        assert RefineState.PAUSED_FOR_HUMAN in REF_TRANSITIONS[RefineState.VERIFIER]

    def test_verifier_can_skip_to_arbitrator(self):
        """If no human input needed, VERIFIER → ARBITRATOR directly."""
        assert RefineState.ARBITRATOR in REF_TRANSITIONS[RefineState.VERIFIER]

    def test_arbitrator_can_converge(self):
        assert RefineState.CONVERGED in REF_TRANSITIONS[RefineState.ARBITRATOR]

    def test_arbitrator_can_loop(self):
        """ARBITRATOR → BUILDER starts a new convergence cycle."""
        assert RefineState.BUILDER in REF_TRANSITIONS[RefineState.ARBITRATOR]

    def test_interrupted_reachable_from_all_active_phases(self):
        """Every active refine phase can transition to INTERRUPTED on failure.

        Active phases are all non-terminal, non-idle, non-pause states —
        i.e. every phase that invokes live LLM/backend work.
        """
        active_phases = (
            RefineState.BUILDER,
            RefineState.CHALLENGER,
            RefineState.PERSONAS,
            RefineState.VERIFIER,
            RefineState.ARBITRATOR,
        )
        for state in active_phases:
            assert RefineState.INTERRUPTED in REF_TRANSITIONS[state], (
                f"{state} must be able to transition to INTERRUPTED"
            )

    def test_all_states_reachable(self):
        targets = _all_targets(REF_TRANSITIONS)
        for state in RefineState:
            if state == RefineState.IDLE:
                continue
            assert state in targets, f"{state} is unreachable"


# ---------------------------------------------------------------------------
# PlanState
# ---------------------------------------------------------------------------

class TestPlanStateMembership:
    def test_idle(self):
        assert PlanState.IDLE in PlanState

    def test_builder(self):
        assert PlanState.BUILDER in PlanState

    def test_challenger(self):
        assert PlanState.CHALLENGER in PlanState

    def test_personas(self):
        assert PlanState.PERSONAS in PlanState

    def test_verifier(self):
        assert PlanState.VERIFIER in PlanState

    def test_paused_for_human(self):
        assert PlanState.PAUSED_FOR_HUMAN in PlanState

    def test_arbitrator(self):
        assert PlanState.ARBITRATOR in PlanState

    def test_converged(self):
        assert PlanState.CONVERGED in PlanState

    def test_interrupted(self):
        assert PlanState.INTERRUPTED in PlanState

    def test_str_values_are_lowercase(self):
        for state in PlanState:
            assert state.value == state.value.lower()


class TestPlanTerminalStates:
    def test_converged_and_interrupted_terminal(self):
        assert PlanState.CONVERGED in PLAN_TERMINAL
        assert PlanState.INTERRUPTED in PLAN_TERMINAL

    def test_idle_not_terminal(self):
        assert PlanState.IDLE not in PLAN_TERMINAL

    def test_paused_for_human_not_terminal(self):
        assert PlanState.PAUSED_FOR_HUMAN not in PLAN_TERMINAL


class TestPlanPauseResume:
    def test_paused_for_human_is_pause_state(self):
        assert PlanState.PAUSED_FOR_HUMAN in PLAN_PAUSE

    def test_pause_transitions_are_resume_states(self):
        for pause_state in PLAN_PAUSE:
            assert PLAN_TRANSITIONS[pause_state] == PLAN_RESUME

    def test_arbitrator_is_resume_target(self):
        assert PlanState.ARBITRATOR in PLAN_RESUME


class TestPlanTransitions:
    def test_transitions_cover_all_states(self):
        assert set(PLAN_TRANSITIONS.keys()) == set(PlanState)

    def test_all_transition_targets_are_valid(self):
        all_states = frozenset(PlanState)
        for state, nexts in PLAN_TRANSITIONS.items():
            assert nexts <= all_states

    def test_terminal_states_have_no_transitions(self):
        for state in PLAN_TERMINAL:
            assert PLAN_TRANSITIONS[state] == frozenset()

    def test_nonterminal_states_have_at_least_one_transition(self):
        nonterminal = frozenset(PlanState) - PLAN_TERMINAL
        for state in nonterminal:
            assert PLAN_TRANSITIONS[state], f"{state} has no transitions"

    def test_all_states_reachable(self):
        targets = _all_targets(PLAN_TRANSITIONS)
        for state in PlanState:
            if state == PlanState.IDLE:
                continue
            assert state in targets, f"{state} is unreachable"

    def test_interrupted_reachable_from_all_active_phases(self):
        """Every active plan phase can transition to INTERRUPTED on failure."""
        active_phases = (
            PlanState.BUILDER,
            PlanState.CHALLENGER,
            PlanState.PERSONAS,
            PlanState.VERIFIER,
            PlanState.ARBITRATOR,
        )
        for state in active_phases:
            assert PlanState.INTERRUPTED in PLAN_TRANSITIONS[state], (
                f"{state} must be able to transition to INTERRUPTED"
            )


# ---------------------------------------------------------------------------
# Cross-mode structural invariants
# ---------------------------------------------------------------------------

class TestCrossModeInvariants:
    """Structural contracts that must hold across all three workflow models."""

    def test_all_three_have_idle(self):
        assert ResearchState.IDLE in ResearchState
        assert RefineState.IDLE in RefineState
        assert PlanState.IDLE in PlanState

    def test_all_three_have_converged_terminal(self):
        assert ResearchState.CONVERGED in R_TERMINAL
        assert RefineState.CONVERGED in REF_TERMINAL
        assert PlanState.CONVERGED in PLAN_TERMINAL

    def test_all_three_have_interrupted_terminal(self):
        assert ResearchState.INTERRUPTED in R_TERMINAL
        assert RefineState.INTERRUPTED in REF_TERMINAL
        assert PlanState.INTERRUPTED in PLAN_TERMINAL

    def test_refine_and_plan_share_pause_semantics(self):
        """Plan and Refine must both have PAUSED_FOR_HUMAN as a pause state."""
        assert RefineState.PAUSED_FOR_HUMAN in REF_PAUSE
        assert PlanState.PAUSED_FOR_HUMAN in PLAN_PAUSE

    def test_research_has_no_pause_states(self):
        assert R_PAUSE == frozenset()

    def test_interrupted_reachable_from_active_phases_in_all_modes(self):
        """All three workflow models must allow INTERRUPTED from every active phase.

        This guards against reverting the full-failure-surface model.
        """
        # research active phases (no pause state; IDLE excluded)
        research_active = frozenset(ResearchState) - R_TERMINAL - {ResearchState.IDLE}
        for state in research_active:
            assert ResearchState.INTERRUPTED in R_TRANSITIONS[state], (
                f"research:{state} must reach INTERRUPTED"
            )
        # refine active phases (exclude PAUSED_FOR_HUMAN — it awaits human input)
        refine_active = frozenset(RefineState) - REF_TERMINAL - {RefineState.IDLE} - REF_PAUSE
        for state in refine_active:
            assert RefineState.INTERRUPTED in REF_TRANSITIONS[state], (
                f"refine:{state} must reach INTERRUPTED"
            )
        # plan active phases (same exclusions)
        plan_active = frozenset(PlanState) - PLAN_TERMINAL - {PlanState.IDLE} - PLAN_PAUSE
        for state in plan_active:
            assert PlanState.INTERRUPTED in PLAN_TRANSITIONS[state], (
                f"plan:{state} must reach INTERRUPTED"
            )
