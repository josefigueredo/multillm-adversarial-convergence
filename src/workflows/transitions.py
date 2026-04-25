"""Workflow state transition emitter.

Provides :class:`WorkflowTransitionEmitter`, a lightweight stateful helper
that emits ``workflow_transition`` audit events as a workflow progresses
through its state machine.

Usage
-----
::

    from src.workflows.research_states import ResearchState
    from src.workflows.transitions import WorkflowTransitionEmitter

    emitter = WorkflowTransitionEmitter(ctx.audit_trail, "research", state.current_workflow_state)
    emitter.transition(ResearchState.HYPOTHESIS, iteration=1)
    emitter.transition(ResearchState.EXECUTE, iteration=1, dimension="safety")
    state.current_workflow_state = emitter.current_state

The emitted events have the shape::

    {
        "event": "workflow_transition",
        "workflow": "<mode>",
        "from_state": "<state_value>",
        "to_state": "<state_value>",
        ...extra fields...
    }

State values are the lowercase string values of the enum members, making
them directly usable in audit-trail queries and diagnostics.
"""

from __future__ import annotations

from typing import Any


class WorkflowTransitionEmitter:
    """Stateful emitter for ``workflow_transition`` audit events.

    One instance should be created per iteration/cycle call and its
    ``current_state`` persisted on the long-lived run-state object so that
    cross-call transitions (e.g. ``arbitrator → builder``) are recorded
    correctly.

    Parameters
    ----------
    audit_trail:
        Any object with an ``emit(event: str, **fields)`` method.
        :class:`~src.audit_trail.NullAuditTrailWriter` is acceptable.
    workflow:
        Name of the workflow mode (``"research"``, ``"refine"``, ``"plan"``).
    initial_state:
        The state the workflow is currently in before the first
        :meth:`transition` call.  This becomes the ``from_state`` of the
        first emitted event.
    """

    def __init__(self, audit_trail: Any, workflow: str, initial_state: Any) -> None:
        self._audit = audit_trail
        self._workflow = workflow
        self._current = initial_state

    def transition(self, to_state: Any, **extra: Any) -> None:
        """Emit a ``workflow_transition`` event and advance the current state.

        Parameters
        ----------
        to_state:
            The state being entered.  Must have a ``.value`` attribute that
            returns a lowercase string (satisfied by all ``str, Enum`` states
            defined in :mod:`src.workflows`).
        **extra:
            Additional fields forwarded verbatim to the audit event (e.g.
            ``iteration``, ``cycle``, ``dimension``).
        """
        self._audit.emit(
            "workflow_transition",
            workflow=self._workflow,
            from_state=self._current.value,
            to_state=to_state.value,
            **extra,
        )
        self._current = to_state

    @property
    def current_state(self) -> Any:
        """The state the workflow is currently in."""
        return self._current
