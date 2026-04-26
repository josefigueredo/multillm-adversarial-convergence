"""HITL workflow gate definitions — MM08 Step 2.

Each :class:`HitlGate` attaches a human-review pause point to a specific
workflow phase or cross-cutting checkpoint.  :data:`GATES_BY_MODE` maps every
intervention mode (from :data:`src.config.VALID_INTERVENTION_MODES`) to the
frozenset of gates that are active under that mode.

Concepts
--------
``workflow``
    One of ``"research"``, ``"refine"``, ``"plan"``, or ``"all"`` for gates
    that apply to every workflow (e.g. the ``"convergence"`` checkpoint at the
    end of Phase 1).

``target``
    The phase name or checkpoint name at which the gate fires.  Phase names
    match the values in :mod:`src.workflows.contracts`.

``target_type``
    :attr:`GateTarget.PHASE` for active workflow phases; :attr:`GateTarget.CHECKPOINT`
    for synthetic milestones (``"convergence"``, ``"run_complete"``).

``trigger``
    :attr:`GateTrigger.BEFORE` — pause before the target begins;
    :attr:`GateTrigger.AFTER` — pause after the target completes.

Intervention mode semantics
---------------------------
``full_auto``
    No human gates.  Fully automated end-to-end.

``checkpoint_only``
    Gate at major milestones: Phase-1 convergence and full-run completion.
    Low interruption; useful for operator oversight without step-by-step review.

``decision_only``
    Gate immediately after key decision phases: the research keep/discard
    decision (``decide``) and the critique-verdict classification (``verifier``
    in refine/plan).

``co_pilot``
    Gate *before* every active phase so a human can review context and steer
    before each step executes.

``step_review``
    Gate *after* every active phase so a human can review the output before
    the next phase begins.  Also gates after Phase-1 convergence.

Usage
-----
::

    from src.workflows.gates import should_pause, GateTrigger

    if should_pause(cfg.hitl.intervention_mode, "research", "hypothesis", GateTrigger.BEFORE):
        # emit paused_for_human and wait for guidance
        ...
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GateTrigger(str, Enum):
    """When a human gate fires relative to its target."""

    BEFORE = "before"
    """Pause before the target phase begins."""

    AFTER = "after"
    """Pause after the target phase completes."""


class GateTarget(str, Enum):
    """Whether the gate is attached to an active phase or a synthetic checkpoint."""

    PHASE = "phase"
    """An active workflow phase (e.g. ``"hypothesis"``, ``"builder"``)."""

    CHECKPOINT = "checkpoint"
    """A synthetic milestone (e.g. ``"convergence"``, ``"run_complete"``)."""


# ---------------------------------------------------------------------------
# HitlGate dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HitlGate:
    """A single configurable human gate attached to a workflow target.

    Attributes
    ----------
    workflow:
        The workflow this gate belongs to — ``"research"``, ``"refine"``,
        ``"plan"``, or ``"all"`` for cross-cutting gates.
    target:
        The phase or checkpoint name at which the gate fires.  Phase names
        match values in :mod:`src.workflows.contracts`.
    target_type:
        Whether ``target`` is an active :attr:`GateTarget.PHASE` or a
        synthetic :attr:`GateTarget.CHECKPOINT`.
    trigger:
        :attr:`GateTrigger.BEFORE` or :attr:`GateTrigger.AFTER`.
    description:
        Human-readable explanation of what this gate is reviewing.
    """

    workflow: str
    target: str
    target_type: GateTarget
    trigger: GateTrigger
    description: str


# ---------------------------------------------------------------------------
# Internal helpers — generate per-workflow gate sets
# ---------------------------------------------------------------------------

_RESEARCH_PHASES = ("hypothesis", "execute", "score", "decide", "merge")
_CONVERGENCE_LOOP_PHASES = ("builder", "challenger", "personas", "verifier", "arbitrator")


def _phase_gates(workflow: str, phases: tuple[str, ...], trigger: GateTrigger) -> frozenset[HitlGate]:
    verb = "Before" if trigger == GateTrigger.BEFORE else "After"
    return frozenset(
        HitlGate(
            workflow=workflow,
            target=phase,
            target_type=GateTarget.PHASE,
            trigger=trigger,
            description=f"{verb} {phase} — review before continuing",
        )
        for phase in phases
    )


# Checkpoint gates are cross-cutting (workflow="all") and always AFTER.
_CHECKPOINT_GATES: frozenset[HitlGate] = frozenset({
    HitlGate(
        workflow="all",
        target="convergence",
        target_type=GateTarget.CHECKPOINT,
        trigger=GateTrigger.AFTER,
        description="Phase 1 convergence reached — review before continuing to expansion",
    ),
    HitlGate(
        workflow="all",
        target="run_complete",
        target_type=GateTarget.CHECKPOINT,
        trigger=GateTrigger.AFTER,
        description="Run complete — review final artifacts",
    ),
})


# ---------------------------------------------------------------------------
# GATES_BY_MODE
# ---------------------------------------------------------------------------

GATES_BY_MODE: dict[str, frozenset[HitlGate]] = {
    "full_auto": frozenset(),
    "checkpoint_only": _CHECKPOINT_GATES,
    "decision_only": frozenset({
        HitlGate(
            workflow="research",
            target="decide",
            target_type=GateTarget.PHASE,
            trigger=GateTrigger.AFTER,
            description="Iteration keep/discard decision — review before committing",
        ),
        HitlGate(
            workflow="refine",
            target="verifier",
            target_type=GateTarget.PHASE,
            trigger=GateTrigger.AFTER,
            description="Critique verdict — review before applying",
        ),
        HitlGate(
            workflow="plan",
            target="verifier",
            target_type=GateTarget.PHASE,
            trigger=GateTrigger.AFTER,
            description="Critique verdict — review before applying",
        ),
    }),
    "co_pilot": (
        _phase_gates("research", _RESEARCH_PHASES, GateTrigger.BEFORE)
        | _phase_gates("refine", _CONVERGENCE_LOOP_PHASES, GateTrigger.BEFORE)
        | _phase_gates("plan", _CONVERGENCE_LOOP_PHASES, GateTrigger.BEFORE)
    ),
    "step_review": (
        _phase_gates("research", _RESEARCH_PHASES, GateTrigger.AFTER)
        | _phase_gates("refine", _CONVERGENCE_LOOP_PHASES, GateTrigger.AFTER)
        | _phase_gates("plan", _CONVERGENCE_LOOP_PHASES, GateTrigger.AFTER)
        | frozenset({
            HitlGate(
                workflow="all",
                target="convergence",
                target_type=GateTarget.CHECKPOINT,
                trigger=GateTrigger.AFTER,
                description="After Phase 1 convergence — review before expansion",
            )
        })
    ),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

VALID_WORKFLOWS: tuple[str, ...] = ("research", "refine", "plan")


def _validate_workflow(workflow: str) -> None:
    if workflow not in VALID_WORKFLOWS:
        raise ValueError(
            f"Unknown workflow: {workflow!r}. "
            f"Must be one of: {', '.join(VALID_WORKFLOWS)}"
        )


def get_gates_for_mode(intervention_mode: str) -> frozenset[HitlGate]:
    """Return all :class:`HitlGate` instances active for *intervention_mode*.

    Raises
    ------
    ValueError
        If *intervention_mode* is not a known mode.
    """
    try:
        return GATES_BY_MODE[intervention_mode]
    except KeyError:
        raise ValueError(
            f"Unknown intervention mode: {intervention_mode!r}. "
            f"Must be one of: {', '.join(GATES_BY_MODE)}"
        )


def get_gates(intervention_mode: str, workflow: str) -> frozenset[HitlGate]:
    """Return the gates for *intervention_mode* that apply to *workflow*.

    Includes both workflow-specific gates and cross-cutting (``"all"``) gates.

    Raises
    ------
    ValueError
        If *intervention_mode* is not a known mode or *workflow* is not a
        recognised workflow name.
    """
    _validate_workflow(workflow)
    all_gates = get_gates_for_mode(intervention_mode)
    return frozenset(g for g in all_gates if g.workflow in (workflow, "all"))


def should_pause(
    intervention_mode: str,
    workflow: str,
    target: str,
    trigger: "GateTrigger | str",
) -> bool:
    """Return ``True`` if the workflow should pause at the given target/trigger.

    Parameters
    ----------
    intervention_mode:
        Active intervention mode (from :data:`src.config.VALID_INTERVENTION_MODES`).
    workflow:
        Current workflow — ``"research"``, ``"refine"``, or ``"plan"``.
    target:
        Phase name or checkpoint name to test.
    trigger:
        :attr:`GateTrigger.BEFORE` or :attr:`GateTrigger.AFTER`.

    Raises
    ------
    ValueError
        If *intervention_mode* is unknown, *workflow* is not a recognised
        workflow name, or *trigger* is not a valid :class:`GateTrigger` value.
    """
    trigger = GateTrigger(trigger)  # validates the trigger value
    relevant = get_gates(intervention_mode, workflow)  # validates workflow
    return any(g.target == target and g.trigger == trigger for g in relevant)
