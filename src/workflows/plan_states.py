"""Plan convergence workflow state machine.

Captures the lifecycle and per-cycle phase states for the plan
convergence loop (``src/plan_loop.py``).

Design contract
---------------
- :class:`PlanState` is the single state vocabulary for the plan
  workflow.  Values are lowercase strings for audit-trail serialisation.
- :data:`TERMINAL_STATES` — states from which no transition is possible.
- :data:`PAUSE_STATES` — states where the workflow waits for human input.
- :data:`RESUME_STATES` — states entered when a pause is resolved.
- :data:`TRANSITIONS` — complete valid transition map.

The plan loop is structurally identical to the refine (document
convergence) loop but operates on a plan document instead of a PRD.
Phase names and transition semantics are therefore the same.

One-cycle happy path
--------------------
::

    IDLE → BUILDER → CHALLENGER → PERSONAS → VERIFIER ─→ PAUSED_FOR_HUMAN
                ↑                                    └──→ ARBITRATOR ─→ BUILDER
                │                                                    └──→ CONVERGED
                └────────────────────────────────────────────────────────
"""

from __future__ import annotations

from enum import Enum


class PlanState(str, Enum):
    """Lifecycle and phase states for the plan convergence loop."""

    IDLE = "idle"
    """Not yet started."""

    BUILDER = "builder"
    """Generating an initial plan or applying pending patches."""

    CHALLENGER = "challenger"
    """Challenging the current plan for issues."""

    PERSONAS = "personas"
    """Gathering persona-specific critique perspectives."""

    VERIFIER = "verifier"
    """Classifying critiques as valid / stale / deferred / human-required."""

    PAUSED_FOR_HUMAN = "paused_for_human"
    """Waiting for human decisions on deferred critiques — a pause state."""

    ARBITRATOR = "arbitrator"
    """Generating patches for valid critiques to be applied next cycle."""

    CONVERGED = "converged"
    """Convergence criterion met (consecutive clean cycles) — terminal."""

    INTERRUPTED = "interrupted"
    """Aborted due to an unrecoverable error — terminal."""


#: States from which the workflow cannot continue.
TERMINAL_STATES: frozenset[PlanState] = frozenset({
    PlanState.CONVERGED,
    PlanState.INTERRUPTED,
})

#: States where the workflow waits for external (human) input.
PAUSE_STATES: frozenset[PlanState] = frozenset({
    PlanState.PAUSED_FOR_HUMAN,
})

#: States entered when resuming from a pause.
#: Exactly matches the valid transitions out of :data:`PAUSE_STATES`.
RESUME_STATES: frozenset[PlanState] = frozenset({
    PlanState.ARBITRATOR,
})

#: Valid transitions: ``{state: frozenset_of_valid_next_states}``.
TRANSITIONS: dict[PlanState, frozenset[PlanState]] = {
    PlanState.IDLE: frozenset({
        PlanState.BUILDER,
    }),
    PlanState.BUILDER: frozenset({
        PlanState.CHALLENGER,
        PlanState.INTERRUPTED,
    }),
    PlanState.CHALLENGER: frozenset({
        PlanState.PERSONAS,
        PlanState.INTERRUPTED,    # unrecoverable failure in challenge step
    }),
    PlanState.PERSONAS: frozenset({
        PlanState.VERIFIER,
        PlanState.INTERRUPTED,    # unrecoverable failure in persona gathering
    }),
    PlanState.VERIFIER: frozenset({
        PlanState.ARBITRATOR,         # no human input needed
        PlanState.PAUSED_FOR_HUMAN,   # human gate triggered
        PlanState.INTERRUPTED,        # unrecoverable failure in verification
    }),
    PlanState.PAUSED_FOR_HUMAN: frozenset({
        PlanState.ARBITRATOR,         # resume after human decisions collected
    }),
    PlanState.ARBITRATOR: frozenset({
        PlanState.BUILDER,      # start next convergence cycle
        PlanState.CONVERGED,    # stopping criterion met
        PlanState.INTERRUPTED,  # unrecoverable failure in patch generation
    }),
    PlanState.CONVERGED: frozenset(),
    PlanState.INTERRUPTED: frozenset(),
}
