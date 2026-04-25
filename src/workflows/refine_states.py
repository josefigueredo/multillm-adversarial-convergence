"""Refine (document convergence) workflow state machine.

Captures the lifecycle and per-cycle phase states for the document
convergence loop (``src/document_loop.py``).

Design contract
---------------
- :class:`RefineState` is the single state vocabulary for the refine
  workflow.  Values are lowercase strings for audit-trail serialisation.
- :data:`TERMINAL_STATES` — states from which no transition is possible.
- :data:`PAUSE_STATES` — states where the workflow waits for human input.
- :data:`RESUME_STATES` — states entered when a pause is resolved.
- :data:`TRANSITIONS` — complete valid transition map.

One-cycle happy path
--------------------
::

    IDLE → BUILDER → CHALLENGER → PERSONAS → VERIFIER ─→ PAUSED_FOR_HUMAN
                ↑                                    └──→ ARBITRATOR ─→ BUILDER
                │                                                    └──→ CONVERGED
                └────────────────────────────────────────────────────────

Human-gate semantics
--------------------
When the verifier finds critiques that require human judgment,
``VERIFIER`` transitions to ``PAUSED_FOR_HUMAN``.  Once the human
decisions are collected, the workflow resumes at ``ARBITRATOR`` (the
first state that acts on those decisions).  When no human input is
needed, ``VERIFIER`` transitions directly to ``ARBITRATOR``.
"""

from __future__ import annotations

from enum import Enum


class RefineState(str, Enum):
    """Lifecycle and phase states for the document convergence loop."""

    IDLE = "idle"
    """Not yet started."""

    BUILDER = "builder"
    """Generating an initial draft or applying pending patches."""

    CHALLENGER = "challenger"
    """Challenging the current document for issues."""

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
TERMINAL_STATES: frozenset[RefineState] = frozenset({
    RefineState.CONVERGED,
    RefineState.INTERRUPTED,
})

#: States where the workflow waits for external (human) input.
PAUSE_STATES: frozenset[RefineState] = frozenset({
    RefineState.PAUSED_FOR_HUMAN,
})

#: States entered when resuming from a pause.
#: Exactly matches the valid transitions out of :data:`PAUSE_STATES`.
RESUME_STATES: frozenset[RefineState] = frozenset({
    RefineState.ARBITRATOR,
})

#: Valid transitions: ``{state: frozenset_of_valid_next_states}``.
TRANSITIONS: dict[RefineState, frozenset[RefineState]] = {
    RefineState.IDLE: frozenset({
        RefineState.BUILDER,
    }),
    RefineState.BUILDER: frozenset({
        RefineState.CHALLENGER,
        RefineState.INTERRUPTED,
    }),
    RefineState.CHALLENGER: frozenset({
        RefineState.PERSONAS,
    }),
    RefineState.PERSONAS: frozenset({
        RefineState.VERIFIER,
    }),
    RefineState.VERIFIER: frozenset({
        RefineState.ARBITRATOR,         # no human input needed
        RefineState.PAUSED_FOR_HUMAN,   # human gate triggered
    }),
    RefineState.PAUSED_FOR_HUMAN: frozenset({
        RefineState.ARBITRATOR,         # resume after human decisions collected
    }),
    RefineState.ARBITRATOR: frozenset({
        RefineState.BUILDER,    # start next convergence cycle
        RefineState.CONVERGED,  # stopping criterion met
    }),
    RefineState.CONVERGED: frozenset(),
    RefineState.INTERRUPTED: frozenset(),
}
