"""Research workflow state machine.

Captures the lifecycle and per-iteration phase states for the autonomous
research loop (``src/research_loop.py``).

Design contract
---------------
- :class:`ResearchState` is the single state vocabulary for the research
  workflow.  Each value is a lowercase string suitable for audit-trail events.
- :data:`TERMINAL_STATES` — states from which no transition is possible;
  the workflow is done.
- :data:`PAUSE_STATES` — states where the workflow is waiting for external
  input (none in the research loop; it has no human-gate).
- :data:`RESUME_STATES` — states the workflow enters after a pause is
  resolved (empty when :data:`PAUSE_STATES` is empty).
- :data:`TRANSITIONS` — the complete valid transition map.  Every
  :class:`ResearchState` key is present; terminal states map to the empty
  frozenset.

Lifecycle
---------
::

    IDLE
     └─→ HYPOTHESIS ──────────────────────────→ CONVERGED
           └─→ EXECUTE → SCORE → DECIDE → MERGE → HYPOTHESIS
                 │         │        │       │
                 └─────────┴────────┴───────┴──────→ INTERRUPTED

Every active phase (HYPOTHESIS through MERGE) can transition to INTERRUPTED
on an unrecoverable error.
"""

from __future__ import annotations

from enum import Enum


class ResearchState(str, Enum):
    """Lifecycle and phase states for the autonomous research loop."""

    IDLE = "idle"
    """Not yet started."""

    HYPOTHESIS = "hypothesis"
    """Selecting the next dimension to explore."""

    EXECUTE = "execute"
    """Invoking a backend to produce research findings."""

    SCORE = "score"
    """Scoring and selecting candidate findings."""

    DECIDE = "decide"
    """Keep or discard the iteration's findings."""

    MERGE = "merge"
    """Merging accepted findings into the knowledge base."""

    CONVERGED = "converged"
    """All dimensions explored or stopping criterion met — terminal."""

    INTERRUPTED = "interrupted"
    """Aborted due to an unrecoverable error — terminal."""


#: States from which the workflow cannot continue.
TERMINAL_STATES: frozenset[ResearchState] = frozenset({
    ResearchState.CONVERGED,
    ResearchState.INTERRUPTED,
})

#: States where the workflow waits for external (human) input.
#: The research loop has no human-gate — this set is intentionally empty.
PAUSE_STATES: frozenset[ResearchState] = frozenset()

#: States the workflow enters when resuming from a pause.
#: Empty because :data:`PAUSE_STATES` is empty.
RESUME_STATES: frozenset[ResearchState] = frozenset()

#: Valid transitions: ``{state: frozenset_of_valid_next_states}``.
#:
#: Reading the happy path:
#:   IDLE → HYPOTHESIS → EXECUTE → SCORE → DECIDE → MERGE → HYPOTHESIS → …
#:   HYPOTHESIS → CONVERGED  (when no dimensions remain)
#:
#: Every active phase can also transition to INTERRUPTED on an unrecoverable
#: error (hypothesis generation, backend execution, scoring, deciding, merging).
TRANSITIONS: dict[ResearchState, frozenset[ResearchState]] = {
    ResearchState.IDLE: frozenset({
        ResearchState.HYPOTHESIS,
    }),
    ResearchState.HYPOTHESIS: frozenset({
        ResearchState.EXECUTE,
        ResearchState.CONVERGED,    # no dimensions left to explore
        ResearchState.INTERRUPTED,  # unrecoverable failure in hypothesis step
    }),
    ResearchState.EXECUTE: frozenset({
        ResearchState.SCORE,
        ResearchState.INTERRUPTED,
    }),
    ResearchState.SCORE: frozenset({
        ResearchState.DECIDE,
        ResearchState.INTERRUPTED,  # unrecoverable failure in scoring/judging
    }),
    ResearchState.DECIDE: frozenset({
        ResearchState.MERGE,        # keep — merge findings
        ResearchState.HYPOTHESIS,   # discard — try next dimension
        ResearchState.INTERRUPTED,  # unrecoverable failure in decision step
    }),
    ResearchState.MERGE: frozenset({
        ResearchState.HYPOTHESIS,   # continue exploring
        ResearchState.CONVERGED,    # stopping criterion now met after merge
        ResearchState.INTERRUPTED,  # unrecoverable failure in merge/compress
    }),
    ResearchState.CONVERGED: frozenset(),
    ResearchState.INTERRUPTED: frozenset(),
}
