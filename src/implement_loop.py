"""Implement loop — state types and context for the adversarial code-task loop.

MM09: Safe Adversarial Implement Mode.

Key design decisions
--------------------
- :class:`ImplementTarget` captures the **target repo contract**: the repo to
  modify, the execution level, and the allowed write roots.  It is *frozen*
  so callers cannot widen the safety boundary after construction.
- ``execution_level`` defaults to ``"patch_only"`` — the safest option that
  never directly mutates any repository.
- :class:`CandidatePatch` is the central artifact: every strategy phase
  receives and/or produces one.
- :class:`TaskState` tracks mutable loop state; ``current_workflow_state`` uses
  :class:`~src.workflows.implement_states.ImplementState` for audit-trail
  compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .workflows.implement_states import ImplementState


#: Execution levels available for implement mode.
#:
#: ``analyze_only``   — no writes; planning and critique only.
#: ``patch_only``     — generate a diff/patch; no direct mutation of any repo.
#: ``isolated_apply`` — apply in a temporary worktree/clone; never the live repo.
VALID_EXECUTION_LEVELS: tuple[str, ...] = (
    "analyze_only",
    "patch_only",
    "isolated_apply",
)


# ---------------------------------------------------------------------------
# Target repo contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImplementTarget:
    """Explicit contract describing the target repository and safety boundaries.

    This is the *first* thing an implement run establishes — it separates the
    planner/orchestrator repo from the repo being modified.

    Attributes
    ----------
    path:
        Filesystem path of the target repository root.
    execution_level:
        One of :data:`VALID_EXECUTION_LEVELS`.  Defaults to ``"patch_only"``
        (safe default — no direct mutation).
    allowed_roots:
        Tuple of paths (relative to *path*) where writes are permitted.
        Empty tuple means "no paths explicitly allowed" — enforcement is a
        Step-4 concern.
    """

    path: Path
    execution_level: str = "patch_only"
    allowed_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if self.execution_level not in VALID_EXECUTION_LEVELS:
            raise ValueError(
                f"Invalid execution_level '{self.execution_level}'. "
                f"Must be one of: {', '.join(VALID_EXECUTION_LEVELS)}"
            )


# ---------------------------------------------------------------------------
# Task and patch artifacts
# ---------------------------------------------------------------------------

@dataclass
class ImplementTask:
    """A single code implementation task.

    Attributes
    ----------
    description:
        Natural-language description of what needs to be implemented.
    target_file_refs:
        Optional hints about which files the task involves.
    """

    description: str
    target_file_refs: tuple[str, ...] = ()


@dataclass
class CandidatePatch:
    """A code patch generated or revised by a strategy phase.

    The ``content`` field holds the patch text (unified diff, file content,
    or any format agreed upon by the builder/arbitrator prompts).  All strategy
    phases operate on :class:`CandidatePatch` rather than raw strings to keep
    the contract explicit.

    Attributes
    ----------
    content:
        The patch/diff text.
    rationale:
        Builder or arbitrator explanation of the change.
    touched_files:
        Files affected by this patch.
    """

    content: str
    rationale: str = ""
    touched_files: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Loop state
# ---------------------------------------------------------------------------

@dataclass
class TaskState:
    """Mutable state for the implement convergence loop.

    Attributes
    ----------
    task:
        The implementation task being worked on.
    cycle:
        Current loop cycle number (0-indexed).
    converged:
        True once the stopping criterion is met.
    patches:
        History of :class:`CandidatePatch` objects produced so far.
    critiques:
        Critiques accumulated in the current cycle (cleared each cycle).
    current_workflow_state:
        Current :class:`~src.workflows.implement_states.ImplementState`.
    """

    task: ImplementTask
    cycle: int = 0
    converged: bool = False
    patches: list[CandidatePatch] = field(default_factory=list)
    critiques: list[Any] = field(default_factory=list)
    current_workflow_state: ImplementState = ImplementState.IDLE
