"""Repair loop — MM10 Step 4.

Adds an explicit repair cycle distinct from generic convergence.

Key design decisions
--------------------
- The repair loop receives injected ``repair_fn`` and ``execute_fn``
  callables, making it fully testable without real execution machinery.
- It is distinct from the adversarial B/C/V/A loop (which critiques patch
  quality).  The repair loop addresses *concrete execution failures*: wrong
  exit codes, missing output patterns, timeouts.
- ``RepairAttempt`` and ``RepairOutcome`` are frozen records so the full
  history is inspectable and serialisable after the loop completes.

Typical flow
------------
1. Caller runs the original plan and collects results + validations.
2. ``RepairLoop.run()`` is called with the initial state.
3. If validation already passes → resolved immediately (0 cycles).
4. Otherwise: diagnose → repair_fn → execute_fn → validate → repeat.
5. Loop stops on resolution or ``max_cycles`` exhaustion.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .execution_diagnosis import DiagnosisArtifact, diagnose_plan
from .execution_plan import ExecutionPlan
from .execution_validator import ExecutionResult, ValidationResult, validate_plan


# ---------------------------------------------------------------------------
# RepairAttempt
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RepairAttempt:
    """Record of one repair cycle.

    Attributes
    ----------
    cycle:
        1-indexed cycle number.
    diagnosis:
        Diagnosis artifacts for the failures that triggered this repair.
    repaired_plan:
        The :class:`~src.execution_plan.ExecutionPlan` produced by
        ``repair_fn`` for this cycle.
    results:
        Execution results after running *repaired_plan*.
    validations:
        Validation results for *results* against *repaired_plan*.
    """

    cycle: int
    diagnosis: tuple[DiagnosisArtifact, ...]
    repaired_plan: ExecutionPlan
    results: tuple[ExecutionResult, ...]
    validations: tuple[ValidationResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "cycle": self.cycle,
            "diagnosis": [d.to_dict() for d in self.diagnosis],
            "repaired_plan": self.repaired_plan.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "validations": [
                {"passed": v.passed, "failures": list(v.failures)}
                for v in self.validations
            ],
        }


# ---------------------------------------------------------------------------
# RepairOutcome
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RepairOutcome:
    """Final outcome of a :class:`RepairLoop` run.

    Attributes
    ----------
    original_plan:
        The plan that was given to the loop before any repairs.
    attempts:
        Ordered tuple of :class:`RepairAttempt` records (empty if the
        initial validation already passed).
    resolved:
        ``True`` if all validations passed after some repair cycle.
    final_plan:
        The plan that produced the passing results, or the last repaired
        plan when the loop stopped without resolving.
    final_results:
        Execution results from the final plan run.
    final_validations:
        Validation results from the final plan run.
    cycles_run:
        Total repair cycles executed (0 if resolved immediately).
    """

    original_plan: ExecutionPlan
    attempts: tuple[RepairAttempt, ...]
    resolved: bool
    final_plan: ExecutionPlan
    final_results: tuple[ExecutionResult, ...]
    final_validations: tuple[ValidationResult, ...]
    cycles_run: int

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "resolved": self.resolved,
            "cycles_run": self.cycles_run,
            "original_plan": self.original_plan.to_dict(),
            "final_plan": self.final_plan.to_dict(),
            "final_results": [r.to_dict() for r in self.final_results],
            "final_validations": [
                {"passed": v.passed, "failures": list(v.failures)}
                for v in self.final_validations
            ],
            "attempts": [a.to_dict() for a in self.attempts],
        }


# ---------------------------------------------------------------------------
# RepairLoop
# ---------------------------------------------------------------------------

#: Type alias for a function that proposes a repaired plan given diagnosis.
RepairFn = Callable[[ExecutionPlan, list[DiagnosisArtifact]], ExecutionPlan]

#: Type alias for a function that executes a plan and returns results.
ExecuteFn = Callable[[ExecutionPlan], list[ExecutionResult]]


class RepairLoop:
    """Orchestrate explicit repair cycles for a failed execution plan.

    Parameters
    ----------
    max_cycles:
        Maximum number of repair iterations.  Must be >= 1.
    """

    def __init__(self, max_cycles: int = 3) -> None:
        if max_cycles < 1:
            raise ValueError(
                f"RepairLoop.max_cycles must be >= 1, got {max_cycles}"
            )
        self._max_cycles = max_cycles

    def run(
        self,
        plan: ExecutionPlan,
        initial_results: list[ExecutionResult],
        initial_validations: list[ValidationResult],
        repair_fn: RepairFn,
        execute_fn: ExecuteFn,
    ) -> RepairOutcome:
        """Execute the repair loop.

        Parameters
        ----------
        plan:
            The original execution plan.
        initial_results:
            Results from the initial run of *plan* (before any repair).
        initial_validations:
            Validation results for *initial_results* against *plan*.
        repair_fn:
            Callable ``(plan, diagnosis) -> repaired_plan``.  Called once
            per cycle with the current plan and its diagnosis artifacts.
        execute_fn:
            Callable ``(repaired_plan) -> results``.  Executes the repaired
            plan and returns a list of :class:`~src.execution_validator.ExecutionResult`.

        Returns
        -------
        RepairOutcome
            Full history of repair attempts and the final state.
        """
        # Entry-contract: lengths must match plan.steps before anything runs.
        n = len(plan.steps)
        if len(initial_results) != n:
            raise ValueError(
                f"initial_results length {len(initial_results)} != plan steps {n}"
            )
        if len(initial_validations) != n:
            raise ValueError(
                f"initial_validations length {len(initial_validations)} != plan steps {n}"
            )

        # Fast path — already passing.
        if all(v.passed for v in initial_validations):
            return RepairOutcome(
                original_plan=plan,
                attempts=(),
                resolved=True,
                final_plan=plan,
                final_results=tuple(initial_results),
                final_validations=tuple(initial_validations),
                cycles_run=0,
            )

        attempts: list[RepairAttempt] = []
        current_plan = plan
        current_results = list(initial_results)
        current_validations = list(initial_validations)

        for cycle in range(1, self._max_cycles + 1):
            # Diagnose the current failures.
            diagnosis = diagnose_plan(current_plan, current_results, current_validations)

            # Ask repair_fn for an improved plan.
            repaired_plan = repair_fn(current_plan, diagnosis)

            # Execute the repaired plan.
            new_results = execute_fn(repaired_plan)

            # Validate the new results.
            new_validations = validate_plan(repaired_plan, new_results)

            attempt = RepairAttempt(
                cycle=cycle,
                diagnosis=tuple(diagnosis),
                repaired_plan=repaired_plan,
                results=tuple(new_results),
                validations=tuple(new_validations),
            )
            attempts.append(attempt)

            current_plan = repaired_plan
            current_results = new_results
            current_validations = new_validations

            if all(v.passed for v in current_validations):
                return RepairOutcome(
                    original_plan=plan,
                    attempts=tuple(attempts),
                    resolved=True,
                    final_plan=current_plan,
                    final_results=tuple(current_results),
                    final_validations=tuple(current_validations),
                    cycles_run=cycle,
                )

        # Exhausted max_cycles without resolving.
        return RepairOutcome(
            original_plan=plan,
            attempts=tuple(attempts),
            resolved=False,
            final_plan=current_plan,
            final_results=tuple(current_results),
            final_validations=tuple(current_validations),
            cycles_run=self._max_cycles,
        )
