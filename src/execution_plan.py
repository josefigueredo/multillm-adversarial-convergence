"""Execution plan model — MM10 Step 1.

Defines the explicit contract for a single execution attempt:
- :class:`ExecutionStep` — one command/tool invocation with expectations
- :class:`TargetContext` — execution environment (working dir, env vars)
- :class:`ExecutionPlan` — ordered sequence of steps + target context

All objects are frozen dataclasses so callers cannot widen the contract
after construction.  ``TargetContext.env_vars`` is stored as a
:class:`types.MappingProxyType` so the nested mapping is also immutable.
All types support ``to_dict()`` / ``from_dict()`` for artifact persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


# ---------------------------------------------------------------------------
# ExecutionStep
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionStep:
    """One executable unit: a command or tool invocation with expectations.

    Attributes
    ----------
    command:
        The shell command or tool invocation string.
    description:
        Human-readable explanation of what this step does.
    expected_exit_code:
        Exit code considered successful.  Defaults to ``0``.
    timeout_seconds:
        Maximum wall-clock seconds allowed for this step.  ``None`` = no limit.
    expected_output_patterns:
        Substrings that must appear in stdout/stderr for the step to be
        considered a pass.  Empty tuple means no output constraint.
    """

    command: str
    description: str = ""
    expected_exit_code: int = 0
    timeout_seconds: int | None = None
    expected_output_patterns: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "command": self.command,
            "description": self.description,
            "expected_exit_code": self.expected_exit_code,
            "timeout_seconds": self.timeout_seconds,
            "expected_output_patterns": list(self.expected_output_patterns),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionStep":
        """Deserialise from a dict produced by :meth:`to_dict`."""
        return cls(
            command=data["command"],
            description=data.get("description", ""),
            expected_exit_code=data.get("expected_exit_code", 0),
            timeout_seconds=data.get("timeout_seconds"),
            expected_output_patterns=tuple(data.get("expected_output_patterns", [])),
        )


# ---------------------------------------------------------------------------
# TargetContext
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetContext:
    """Execution environment for an :class:`ExecutionPlan`.

    Attributes
    ----------
    working_dir:
        Filesystem directory in which steps execute.
    env_vars:
        Extra environment variables to inject.  Returned as an immutable
        :class:`~types.MappingProxyType` so the env contract cannot be
        widened after construction.
    description:
        Human-readable label for the environment.
    """

    working_dir: Path
    # Stored as MappingProxyType so the nested mapping is genuinely immutable.
    env_vars: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    description: str = ""

    def __init__(
        self,
        working_dir: Path,
        env_vars: dict[str, str] | MappingProxyType | None = None,
        description: str = "",
    ) -> None:
        object.__setattr__(self, "working_dir", working_dir)
        raw = env_vars if env_vars is not None else {}
        proxy = MappingProxyType(dict(raw))  # copy + freeze
        object.__setattr__(self, "env_vars", proxy)
        object.__setattr__(self, "description", description)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "working_dir": str(self.working_dir.resolve()),
            "env_vars": dict(self.env_vars),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetContext":
        """Deserialise from a dict produced by :meth:`to_dict`."""
        return cls(
            working_dir=Path(data["working_dir"]),
            env_vars=dict(data.get("env_vars", {})),
            description=data.get("description", ""),
        )


# ---------------------------------------------------------------------------
# ExecutionPlan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionPlan:
    """Ordered sequence of execution steps with a shared target context.

    Attributes
    ----------
    steps:
        Non-empty tuple of :class:`ExecutionStep` objects executed in order.
    target:
        Execution environment shared by all steps.
    description:
        Human-readable summary of what this plan accomplishes.
    """

    steps: tuple[ExecutionStep, ...]
    target: TargetContext
    description: str = ""

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError(
                "ExecutionPlan requires at least one step — steps tuple is empty"
            )
        if not self.target.working_dir.exists():
            raise ValueError(
                f"ExecutionPlan.target.working_dir does not exist: "
                f"{self.target.working_dir}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "description": self.description,
            "target": self.target.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionPlan":
        """Deserialise from a dict produced by :meth:`to_dict`."""
        return cls(
            steps=tuple(ExecutionStep.from_dict(s) for s in data["steps"]),
            target=TargetContext.from_dict(data["target"]),
            description=data.get("description", ""),
        )

