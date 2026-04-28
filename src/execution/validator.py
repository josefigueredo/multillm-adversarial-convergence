"""Execution validator layer — MM10 Step 2.

Separates validation from criticism.  A *validator* checks a concrete
execution outcome (captured stdout/stderr, exit code, timeout flag) against
the expectations declared in an :class:`~src.execution_plan.ExecutionStep`.
It is purely functional — no I/O, no side effects, no LLM calls.

Key types
---------
:class:`ExecutionResult`
    The captured output of running one :class:`~src.execution_plan.ExecutionStep`.
:class:`ValidationResult`
    The outcome of validating one :class:`ExecutionResult` against one step.
:func:`validate_step`
    Validate a single result against a single step's expectations.
:func:`validate_plan`
    Validate an ordered list of results against an :class:`~src.execution_plan.ExecutionPlan`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.execution.plan import ExecutionPlan, ExecutionStep


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionResult:
    """Captured output from executing one :class:`~src.execution_plan.ExecutionStep`.

    Attributes
    ----------
    exit_code:
        The process exit code (or synthetic code if the step was not run).
    stdout:
        Standard output captured from the step.
    stderr:
        Standard error captured from the step.
    timed_out:
        ``True`` if the step was killed because it exceeded its timeout.
    duration_seconds:
        Wall-clock seconds the step took.  ``None`` if not measured.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionResult":
        """Deserialise from a dict produced by :meth:`to_dict`."""
        return cls(
            exit_code=data["exit_code"],
            stdout=data["stdout"],
            stderr=data["stderr"],
            timed_out=data.get("timed_out", False),
            duration_seconds=data.get("duration_seconds"),
        )


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one :class:`ExecutionResult` against a step.

    Attributes
    ----------
    step:
        The :class:`~src.execution_plan.ExecutionStep` whose expectations
        were checked.
    failures:
        Tuple of human-readable failure messages.  Empty means the step
        passed all checks.
    """

    step: ExecutionStep
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """``True`` when no failures were recorded."""
        return len(self.failures) == 0


# ---------------------------------------------------------------------------
# validate_step()
# ---------------------------------------------------------------------------

def validate_step(step: ExecutionStep, result: ExecutionResult) -> ValidationResult:
    """Validate *result* against *step*'s expectations.

    Checks performed (in order):
    1. Timeout — if ``result.timed_out`` is ``True``, always a failure.
    2. Exit code — ``result.exit_code`` must equal ``step.expected_exit_code``.
    3. Output patterns — each pattern in ``step.expected_output_patterns``
       must appear somewhere in ``result.stdout + result.stderr``.

    All failures are collected before returning; the caller sees the full
    picture in a single call.

    Parameters
    ----------
    step:
        Step whose expectations to validate against.
    result:
        The captured execution outcome.

    Returns
    -------
    ValidationResult
        ``passed`` is ``True`` iff ``failures`` is empty.
    """
    failures: list[str] = []
    combined_output = result.stdout + result.stderr

    if result.timed_out:
        failures.append(
            f"step timed out (timeout_seconds={step.timeout_seconds})"
        )

    if result.exit_code != step.expected_exit_code:
        failures.append(
            f"exit code mismatch: expected {step.expected_exit_code}, "
            f"got {result.exit_code}"
        )

    for pattern in step.expected_output_patterns:
        if pattern not in combined_output:
            failures.append(
                f"expected output pattern not found: {pattern!r}"
            )

    return ValidationResult(step=step, failures=tuple(failures))


# ---------------------------------------------------------------------------
# validate_plan()
# ---------------------------------------------------------------------------

def validate_plan(
    plan: ExecutionPlan,
    results: list[ExecutionResult],
) -> list[ValidationResult]:
    """Validate an ordered list of execution results against *plan*.

    Each result is validated against the step at the same index.

    Parameters
    ----------
    plan:
        The execution plan whose steps define the expectations.
    results:
        One :class:`ExecutionResult` per step, in the same order as
        ``plan.steps``.

    Returns
    -------
    list[ValidationResult]
        One :class:`ValidationResult` per step, in order.

    Raises
    ------
    ValueError
        If the number of results does not match the number of steps.
    """
    if len(results) != len(plan.steps):
        raise ValueError(
            f"validate_plan: number of results ({len(results)}) does not match "
            f"number of plan steps ({len(plan.steps)})"
        )
    return [validate_step(step, result) for step, result in zip(plan.steps, results)]
