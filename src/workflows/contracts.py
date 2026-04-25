"""Workflow phase contracts — MM07 Step 3.

Each active phase in the research, refine, and plan workflows has a
machine-readable :class:`PhaseContract` that captures:

- what inputs the phase consumes
- what outputs it produces
- the done criterion (human-readable)
- whether a soft failure allows the outer loop to retry
- the maximum number of additional retry attempts
- whether this phase may trigger a human-input gate

Usage
-----
::

    from src.workflows.contracts import get_contract

    contract = get_contract("research", "hypothesis")
    if contract and contract.human_gate:
        ...

Contracts are defined only for **active** phases — not for terminal states
(``converged``, ``interrupted``), pause states (``paused_for_human``), or
the ``idle`` pseudo-state.  :func:`get_contract` returns ``None`` for any
phase without a contract.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseContract:
    """Machine-readable specification for one workflow phase.

    Attributes
    ----------
    phase:
        The phase name — matches the string value of the corresponding
        workflow state enum member (e.g. ``"hypothesis"``).
    inputs:
        Named inputs that this phase consumes from the run-state context.
    outputs:
        Named outputs this phase produces and writes back to run state.
    done_criterion:
        Human-readable description of the condition that marks this phase
        as successfully completed.
    retryable:
        ``True`` if a soft failure in this phase allows the outer loop to
        continue (e.g. skip the iteration and try again next time).
        ``False`` if failure is unrecoverable at the phase level.
    max_retries:
        Number of additional retry attempts after the first failure
        (``0`` means no explicit retry beyond the first attempt).
    human_gate:
        ``True`` if this phase may produce outputs that trigger a
        human-input pause before the next phase runs.
    """

    phase: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    done_criterion: str
    retryable: bool
    max_retries: int
    human_gate: bool


# ---------------------------------------------------------------------------
# Research workflow contracts
# ---------------------------------------------------------------------------

RESEARCH_CONTRACTS: dict[str, PhaseContract] = {
    "hypothesis": PhaseContract(
        phase="hypothesis",
        inputs=("knowledge_base", "explored_dimensions", "dimension_attempts", "topic", "goal"),
        outputs=("dimension", "questions", "approach", "rationale"),
        done_criterion="Non-empty hypothesis dict containing dimension and questions",
        retryable=True,
        max_retries=0,
        human_gate=False,
    ),
    "execute": PhaseContract(
        phase="execute",
        inputs=("dimension", "questions", "approach", "knowledge_base"),
        outputs=("findings",),
        done_criterion="Non-empty findings string from backend research execution",
        retryable=True,
        max_retries=0,
        human_gate=False,
    ),
    "score": PhaseContract(
        phase="score",
        inputs=("dimension", "findings", "knowledge_base"),
        outputs=("iteration_score",),
        done_criterion="IterationScore with coverage, quality, and total fields computed",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "decide": PhaseContract(
        phase="decide",
        inputs=("iteration_score", "prev_best_score"),
        outputs=("kept",),
        done_criterion="Keep/discard decision recorded based on score threshold",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "merge": PhaseContract(
        phase="merge",
        inputs=("findings", "knowledge_base", "iteration_score"),
        outputs=("knowledge_base",),
        done_criterion="Accepted findings merged into knowledge base",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
}

# ---------------------------------------------------------------------------
# Refine workflow contracts
# ---------------------------------------------------------------------------

REFINE_CONTRACTS: dict[str, PhaseContract] = {
    "builder": PhaseContract(
        phase="builder",
        inputs=("prd", "pending_patches"),
        outputs=("prd",),
        done_criterion="PRD updated with all pending patches applied",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "challenger": PhaseContract(
        phase="challenger",
        inputs=("prd",),
        outputs=("raw_critiques",),
        done_criterion="Challenger critique generated against current PRD",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "personas": PhaseContract(
        phase="personas",
        inputs=("prd", "persona_configs"),
        outputs=("persona_critiques",),
        done_criterion="Critiques gathered from all configured personas",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "verifier": PhaseContract(
        phase="verifier",
        inputs=("prd", "raw_critiques", "persona_critiques"),
        outputs=("valid_issues", "stale_issues", "deferred_issues", "human_required_issues"),
        done_criterion="All critiques classified as valid, stale, deferred, or human-required",
        retryable=False,
        max_retries=0,
        human_gate=True,
    ),
    "arbitrator": PhaseContract(
        phase="arbitrator",
        inputs=("prd", "valid_issues", "human_decisions"),
        outputs=("patches",),
        done_criterion="Patches generated for all valid issues to be applied next cycle",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
}

# ---------------------------------------------------------------------------
# Plan workflow contracts
# ---------------------------------------------------------------------------
# The plan loop is structurally identical to the refine loop but operates on
# a plan document instead of a PRD.  Phase names and semantics are the same.

PLAN_CONTRACTS: dict[str, PhaseContract] = {
    "builder": PhaseContract(
        phase="builder",
        inputs=("plan", "pending_patches"),
        outputs=("plan",),
        done_criterion="Plan updated with all pending patches applied",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "challenger": PhaseContract(
        phase="challenger",
        inputs=("plan",),
        outputs=("raw_critiques",),
        done_criterion="Challenger critique generated against current plan",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "personas": PhaseContract(
        phase="personas",
        inputs=("plan", "persona_configs"),
        outputs=("persona_critiques",),
        done_criterion="Critiques gathered from all configured personas",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
    "verifier": PhaseContract(
        phase="verifier",
        inputs=("plan", "raw_critiques", "persona_critiques"),
        outputs=("valid_issues", "stale_issues", "deferred_issues", "human_required_issues"),
        done_criterion="All critiques classified as valid, stale, deferred, or human-required",
        retryable=False,
        max_retries=0,
        human_gate=True,
    ),
    "arbitrator": PhaseContract(
        phase="arbitrator",
        inputs=("plan", "valid_issues", "human_decisions"),
        outputs=("patches",),
        done_criterion="Patches generated for all valid issues to be applied next cycle",
        retryable=False,
        max_retries=0,
        human_gate=False,
    ),
}

# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

_WORKFLOW_CONTRACTS: dict[str, dict[str, PhaseContract]] = {
    "research": RESEARCH_CONTRACTS,
    "refine": REFINE_CONTRACTS,
    "plan": PLAN_CONTRACTS,
}


def get_contract(workflow: str, phase: str) -> PhaseContract | None:
    """Return the :class:`PhaseContract` for a given workflow and phase, or ``None``.

    Returns ``None`` for:
    - unknown workflow names
    - terminal states (``converged``, ``interrupted``)
    - the ``idle`` pseudo-state
    - pause states (``paused_for_human``)
    - any other phase name not covered by the contracts

    Parameters
    ----------
    workflow:
        One of ``"research"``, ``"refine"``, or ``"plan"``.
    phase:
        The phase string value (e.g. ``"hypothesis"``, ``"builder"``).
    """
    return _WORKFLOW_CONTRACTS.get(workflow, {}).get(phase)
