"""Implement workflow state machine — MM09.

Captures the lifecycle and per-cycle phase states for the adversarial
implementation loop (``src/implement_loop.py``).

Design contract
---------------
- :class:`ImplementState` is the single state vocabulary for the implement
  workflow.  Values are lowercase strings for audit-trail serialisation.
- :data:`TERMINAL_STATES` — states from which no transition is possible.
- :data:`PAUSE_STATES` — states where the workflow waits for human input.
- :data:`RESUME_STATES` — states entered when a pause is resolved.
- :data:`TRANSITIONS` — complete valid transition map.

One-cycle happy path
--------------------
::

    IDLE → BUILDER → CHALLENGER → VERIFIER ─→ PAUSED_FOR_HUMAN
               ↑                         └──→ ARBITRATOR ─→ BUILDER
               │                                         └──→ CONVERGED
               └─────────────────────────────────────────────

Human-gate semantics
--------------------
Same as refine/plan: ``VERIFIER`` transitions to ``PAUSED_FOR_HUMAN`` when
critiques require human judgment.  After human decisions are collected the
workflow resumes at ``ARBITRATOR``.
"""

from __future__ import annotations

from enum import Enum


class ImplementState(str, Enum):
    """Lifecycle and phase states for the implement loop."""

    IDLE = "idle"
    """Not yet started."""

    BUILDER = "builder"
    """Generating an initial patch or applying revisions from the arbitrator."""

    CHALLENGER = "challenger"
    """Challenging the candidate patch for correctness, regressions, and fit."""

    VERIFIER = "verifier"
    """Classifying critiques as valid / stale / deferred / human-required."""

    PAUSED_FOR_HUMAN = "paused_for_human"
    """Waiting for human decisions on deferred critiques — a pause state."""

    ARBITRATOR = "arbitrator"
    """Producing a revised patch from accepted critiques."""

    CONVERGED = "converged"
    """Convergence criterion met — terminal."""

    INTERRUPTED = "interrupted"
    """Aborted due to an unrecoverable error — terminal."""


#: States from which the workflow cannot continue.
TERMINAL_STATES: frozenset[ImplementState] = frozenset({
    ImplementState.CONVERGED,
    ImplementState.INTERRUPTED,
})

#: States where the workflow waits for external (human) input.
PAUSE_STATES: frozenset[ImplementState] = frozenset({
    ImplementState.PAUSED_FOR_HUMAN,
})

#: States entered when resuming from a pause.
RESUME_STATES: frozenset[ImplementState] = frozenset({
    ImplementState.ARBITRATOR,
})

#: Valid transitions: ``{state: frozenset_of_valid_next_states}``.
TRANSITIONS: dict[ImplementState, frozenset[ImplementState]] = {
    ImplementState.IDLE: frozenset({
        ImplementState.BUILDER,
    }),
    ImplementState.BUILDER: frozenset({
        ImplementState.CHALLENGER,
        ImplementState.INTERRUPTED,
    }),
    ImplementState.CHALLENGER: frozenset({
        ImplementState.VERIFIER,
        ImplementState.INTERRUPTED,
    }),
    ImplementState.VERIFIER: frozenset({
        ImplementState.ARBITRATOR,
        ImplementState.PAUSED_FOR_HUMAN,
        ImplementState.INTERRUPTED,
    }),
    ImplementState.PAUSED_FOR_HUMAN: frozenset({
        ImplementState.ARBITRATOR,
    }),
    ImplementState.ARBITRATOR: frozenset({
        ImplementState.BUILDER,
        ImplementState.CONVERGED,
        ImplementState.INTERRUPTED,
    }),
    ImplementState.CONVERGED: frozenset(),
    ImplementState.INTERRUPTED: frozenset(),
}
