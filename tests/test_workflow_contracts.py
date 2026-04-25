"""Tests for workflow phase contracts — MM07 Step 3."""

from __future__ import annotations

import dataclasses

import pytest

from src.workflows.contracts import (
    PhaseContract,
    RESEARCH_CONTRACTS,
    REFINE_CONTRACTS,
    PLAN_CONTRACTS,
    get_contract,
)
from src.workflows.research_states import ResearchState
from src.workflows.research_states import TERMINAL_STATES as RESEARCH_TERMINAL
from src.workflows.refine_states import RefineState
from src.workflows.refine_states import TERMINAL_STATES as REFINE_TERMINAL
from src.workflows.refine_states import PAUSE_STATES as REFINE_PAUSE
from src.workflows.plan_states import PlanState
from src.workflows.plan_states import TERMINAL_STATES as PLAN_TERMINAL
from src.workflows.plan_states import PAUSE_STATES as PLAN_PAUSE


# ---------------------------------------------------------------------------
# PhaseContract data model
# ---------------------------------------------------------------------------

class TestPhaseContractModel:
    def test_is_frozen_dataclass(self):
        contract = PhaseContract(
            phase="test",
            inputs=("a",),
            outputs=("b",),
            done_criterion="b is set",
            retryable=False,
            max_retries=0,
            human_gate=False,
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            contract.phase = "other"  # direct assignment triggers FrozenInstanceError

    def test_fields_accessible(self):
        contract = PhaseContract(
            phase="hypothesis",
            inputs=("knowledge_base",),
            outputs=("dimension", "questions"),
            done_criterion="non-empty hypothesis dict",
            retryable=True,
            max_retries=0,
            human_gate=False,
        )
        assert contract.phase == "hypothesis"
        assert "knowledge_base" in contract.inputs
        assert "dimension" in contract.outputs
        assert contract.retryable is True
        assert contract.max_retries == 0
        assert contract.human_gate is False

    def test_inputs_and_outputs_are_tuples(self):
        contract = PhaseContract(
            phase="x",
            inputs=("a", "b"),
            outputs=("c",),
            done_criterion="done",
            retryable=False,
            max_retries=0,
            human_gate=False,
        )
        assert isinstance(contract.inputs, tuple)
        assert isinstance(contract.outputs, tuple)

    def test_equality(self):
        a = PhaseContract("p", ("x",), ("y",), "done", False, 0, False)
        b = PhaseContract("p", ("x",), ("y",), "done", False, 0, False)
        assert a == b


# ---------------------------------------------------------------------------
# Research contracts
# ---------------------------------------------------------------------------

class TestResearchContracts:
    def _active_phases(self) -> set[str]:
        return {
            s.value for s in ResearchState
            if s not in RESEARCH_TERMINAL and s != ResearchState.IDLE
        }

    def test_all_active_phases_have_contracts(self):
        for phase in self._active_phases():
            assert phase in RESEARCH_CONTRACTS, f"Missing contract for research phase: {phase}"

    def test_terminal_states_not_in_contracts(self):
        for s in RESEARCH_TERMINAL:
            assert s.value not in RESEARCH_CONTRACTS, f"Terminal state {s.value} should not have a contract"

    def test_idle_not_in_contracts(self):
        assert ResearchState.IDLE.value not in RESEARCH_CONTRACTS

    def test_hypothesis_contract(self):
        c = RESEARCH_CONTRACTS["hypothesis"]
        assert c.phase == "hypothesis"
        assert len(c.inputs) > 0
        assert len(c.outputs) > 0
        assert c.done_criterion
        assert c.retryable is True
        assert c.human_gate is False

    def test_execute_contract_is_retryable(self):
        assert RESEARCH_CONTRACTS["execute"].retryable is True

    def test_score_contract_not_retryable(self):
        assert RESEARCH_CONTRACTS["score"].retryable is False

    def test_decide_contract_not_retryable(self):
        assert RESEARCH_CONTRACTS["decide"].retryable is False

    def test_merge_contract_not_retryable(self):
        assert RESEARCH_CONTRACTS["merge"].retryable is False

    def test_no_research_phase_has_human_gate(self):
        for name, c in RESEARCH_CONTRACTS.items():
            assert c.human_gate is False, f"Research phase {name} should not have human_gate"

    def test_contract_phase_matches_key(self):
        for key, c in RESEARCH_CONTRACTS.items():
            assert c.phase == key

    def test_hypothesis_outputs_include_dimension_and_questions(self):
        c = RESEARCH_CONTRACTS["hypothesis"]
        assert "dimension" in c.outputs
        assert "questions" in c.outputs

    def test_execute_outputs_include_findings(self):
        assert "findings" in RESEARCH_CONTRACTS["execute"].outputs

    def test_merge_inputs_include_findings_and_knowledge_base(self):
        c = RESEARCH_CONTRACTS["merge"]
        assert "findings" in c.inputs
        assert "knowledge_base" in c.inputs


# ---------------------------------------------------------------------------
# Refine contracts
# ---------------------------------------------------------------------------

class TestRefineContracts:
    def _active_phases(self) -> set[str]:
        return {
            s.value for s in RefineState
            if s not in REFINE_TERMINAL
            and s not in REFINE_PAUSE
            and s != RefineState.IDLE
        }

    def test_all_active_phases_have_contracts(self):
        for phase in self._active_phases():
            assert phase in REFINE_CONTRACTS, f"Missing contract for refine phase: {phase}"

    def test_terminal_and_pause_not_in_contracts(self):
        excluded = list(REFINE_TERMINAL) + list(REFINE_PAUSE)
        for s in excluded:
            assert s.value not in REFINE_CONTRACTS

    def test_idle_not_in_contracts(self):
        assert RefineState.IDLE.value not in REFINE_CONTRACTS

    def test_verifier_has_human_gate(self):
        assert REFINE_CONTRACTS["verifier"].human_gate is True

    def test_builder_no_human_gate(self):
        assert REFINE_CONTRACTS["builder"].human_gate is False

    def test_arbitrator_no_human_gate(self):
        assert REFINE_CONTRACTS["arbitrator"].human_gate is False

    def test_contract_phase_matches_key(self):
        for key, c in REFINE_CONTRACTS.items():
            assert c.phase == key

    def test_builder_inputs_include_document(self):
        c = REFINE_CONTRACTS["builder"]
        assert any("prd" in inp or "document" in inp for inp in c.inputs)

    def test_arbitrator_inputs_include_valid_issues(self):
        c = REFINE_CONTRACTS["arbitrator"]
        assert any("issue" in inp or "patch" in inp or "valid" in inp for inp in c.inputs)


# ---------------------------------------------------------------------------
# Plan contracts
# ---------------------------------------------------------------------------

class TestPlanContracts:
    def _active_phases(self) -> set[str]:
        return {
            s.value for s in PlanState
            if s not in PLAN_TERMINAL
            and s not in PLAN_PAUSE
            and s != PlanState.IDLE
        }

    def test_all_active_phases_have_contracts(self):
        for phase in self._active_phases():
            assert phase in PLAN_CONTRACTS, f"Missing contract for plan phase: {phase}"

    def test_verifier_has_human_gate(self):
        assert PLAN_CONTRACTS["verifier"].human_gate is True

    def test_plan_contracts_match_refine_phase_set(self):
        assert set(PLAN_CONTRACTS.keys()) == set(REFINE_CONTRACTS.keys())

    def test_contract_phase_matches_key(self):
        for key, c in PLAN_CONTRACTS.items():
            assert c.phase == key


# ---------------------------------------------------------------------------
# get_contract() lookup
# ---------------------------------------------------------------------------

class TestGetContract:
    def test_returns_contract_for_known_research_phase(self):
        c = get_contract("research", "hypothesis")
        assert c is not None
        assert c.phase == "hypothesis"

    def test_returns_contract_for_known_refine_phase(self):
        c = get_contract("refine", "verifier")
        assert c is not None
        assert c.human_gate is True

    def test_returns_contract_for_known_plan_phase(self):
        c = get_contract("plan", "builder")
        assert c is not None

    def test_returns_none_for_terminal_research_state(self):
        assert get_contract("research", "converged") is None
        assert get_contract("research", "interrupted") is None

    def test_returns_none_for_terminal_refine_state(self):
        assert get_contract("refine", "converged") is None
        assert get_contract("refine", "interrupted") is None

    def test_returns_none_for_idle(self):
        assert get_contract("research", "idle") is None

    def test_returns_none_for_unknown_workflow(self):
        assert get_contract("unknown_mode", "hypothesis") is None

    def test_returns_none_for_unknown_phase(self):
        assert get_contract("research", "nonexistent") is None

    def test_returns_none_for_pause_state(self):
        assert get_contract("refine", "paused_for_human") is None
