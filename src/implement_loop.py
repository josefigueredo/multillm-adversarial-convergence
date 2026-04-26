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
        for root in self.allowed_roots:
            root_path = root if isinstance(root, Path) else Path(root)
            if root_path.is_absolute():
                raise ValueError(
                    f"allowed_roots must be relative paths (not absolute): {root}"
                )
            if ".." in root_path.parts:
                raise ValueError(
                    f"allowed_roots must not contain parent traversal: {root}"
                )



# ---------------------------------------------------------------------------
# Implement config (loaded from YAML)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImplementConfig:
    """Top-level configuration for an implement run.

    Attributes
    ----------
    target:
        Explicit target-repo contract: path, execution level, allowed roots.
    """

    target: ImplementTarget

    @classmethod
    def from_yaml(cls, path: Path) -> "ImplementConfig":
        """Load and validate an implement config from a YAML file.

        Parameters
        ----------
        path:
            Path to the config YAML file.

        Raises
        ------
        OSError
            If the file cannot be read.
        ValueError
            If the YAML is malformed or the config contract is not satisfied.
        """
        import yaml  # lazy import — matches project convention

        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML in implement config: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(
                "Implement config must be a YAML mapping at the top level"
            )

        target_data = raw.get("target")
        if not isinstance(target_data, dict):
            raise ValueError(
                "Implement config must have a 'target' mapping "
                "(e.g.  target:\\n  path: /path/to/repo)"
            )

        target_path_str = target_data.get("path")
        if not target_path_str or not isinstance(target_path_str, str):
            raise ValueError(
                "Implement config must specify target.path as a non-empty string"
            )

        # Resolve relative paths against the config file's own directory so
        # behaviour is not CWD-dependent.
        target_path = Path(target_path_str)
        if not target_path.is_absolute():
            target_path = (path.parent / target_path).resolve()

        if not target_path.exists():
            raise ValueError(
                f"Implement target path does not exist: {target_path}"
            )
        if not target_path.is_dir():
            raise ValueError(
                f"Implement target path must be a directory, not a file: {target_path}"
            )

        execution_level = target_data.get("execution_level", "patch_only")
        if not isinstance(execution_level, str):
            raise ValueError(
                f"target.execution_level must be a string, got "
                f"{type(execution_level).__name__!r}"
            )

        allowed_roots_raw = target_data.get("allowed_roots", [])
        if not isinstance(allowed_roots_raw, (list, tuple)):
            raise ValueError(
                "target.allowed_roots must be a list of relative path strings"
            )
        if not all(isinstance(r, str) for r in allowed_roots_raw):
            raise ValueError(
                "target.allowed_roots entries must all be strings"
            )
        allowed_roots = tuple(Path(r) for r in allowed_roots_raw)

        return cls(
            target=ImplementTarget(
                path=target_path,
                execution_level=execution_level,
                allowed_roots=allowed_roots,
            )
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
