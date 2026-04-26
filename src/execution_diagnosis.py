"""Diagnosis artifacts — MM10 Step 3.

Emits structured diagnosis artifacts when execution or validation fails.
Pure functions — no I/O except :func:`persist_diagnosis`.

Key types and functions
-----------------------
:class:`DiagnosisArtifact`
    Frozen record of a failed step: the step, its result, the validation
    outcome, a classified ``diagnosis_type``, and a human-readable ``summary``.
:func:`diagnose_step`
    Return a :class:`DiagnosisArtifact` for a failed validation, or ``None``
    if the step passed.
:func:`diagnose_plan`
    Return one artifact per failed step in the plan.
:func:`persist_diagnosis`
    Write the artifact list to ``diagnosis.json`` in an output directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .execution_plan import ExecutionPlan, ExecutionStep
from .execution_validator import ExecutionResult, ValidationResult


# ---------------------------------------------------------------------------
# DiagnosisArtifact
# ---------------------------------------------------------------------------

#: Recognised failure categories.
_DIAGNOSIS_TYPES = ("timeout", "exit_code_mismatch", "pattern_missing", "multiple")


@dataclass(frozen=True)
class DiagnosisArtifact:
    """Rich frozen record of a failed execution step.

    Attributes
    ----------
    step:
        The :class:`~src.execution_plan.ExecutionStep` that was run.
    result:
        The :class:`~src.execution_validator.ExecutionResult` that was captured.
    validation:
        The :class:`~src.execution_validator.ValidationResult` that detected
        the failure.
    diagnosis_type:
        Failure category — one of ``"timeout"``, ``"exit_code_mismatch"``,
        ``"pattern_missing"``, or ``"multiple"`` (when more than one check
        failed).
    summary:
        Human-readable single-line summary for operator inspection.
    """

    step: ExecutionStep
    result: ExecutionResult
    validation: ValidationResult
    diagnosis_type: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "step": self.step.to_dict(),
            "result": self.result.to_dict(),
            "diagnosis_type": self.diagnosis_type,
            "summary": self.summary,
            "failures": list(self.validation.failures),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DiagnosisArtifact":
        """Deserialise from a dict produced by :meth:`to_dict`.

        The ``validation`` field is reconstructed from the persisted
        ``failures`` list and the step; the original ``ExecutionResult``
        is also restored.
        """
        step = ExecutionStep.from_dict(data["step"])
        result = ExecutionResult.from_dict(data["result"])
        validation = ValidationResult(
            step=step,
            failures=tuple(data.get("failures", [])),
        )
        return cls(
            step=step,
            result=result,
            validation=validation,
            diagnosis_type=data["diagnosis_type"],
            summary=data["summary"],
        )


# ---------------------------------------------------------------------------
# diagnose_step()
# ---------------------------------------------------------------------------

def diagnose_step(
    step: ExecutionStep,
    result: ExecutionResult,
    validation: ValidationResult,
) -> DiagnosisArtifact | None:
    """Build a diagnosis artifact for *step* if its validation failed.

    Returns ``None`` when ``validation.passed`` is ``True`` so callers can
    use a simple ``if artifact := diagnose_step(...)`` pattern.

    The ``diagnosis_type`` is inferred from the failure set:
    - ``"timeout"``           — only failure is a timeout
    - ``"exit_code_mismatch"``— only failure is an exit-code mismatch
    - ``"pattern_missing"``   — only failures are missing output patterns
    - ``"multiple"``          — two or more distinct failure categories

    Parameters
    ----------
    step:
        The step whose expectations were checked.
    result:
        The captured execution output.
    validation:
        Pre-computed :class:`~src.execution_validator.ValidationResult`
        from :func:`~src.execution_validator.validate_step`.

    Returns
    -------
    DiagnosisArtifact | None
    """
    if validation.passed:
        return None

    failures = validation.failures
    dtype = _classify_diagnosis_type(failures)
    summary = _build_summary(step, result, failures)

    return DiagnosisArtifact(
        step=step,
        result=result,
        validation=validation,
        diagnosis_type=dtype,
        summary=summary,
    )


def _classify_diagnosis_type(failures: tuple[str, ...]) -> str:
    """Return the most specific diagnosis type for a set of failure messages."""
    has_timeout = any("timeout" in f.lower() or "timed" in f.lower() for f in failures)
    has_exit = any("exit code" in f.lower() for f in failures)
    has_pattern = any("pattern" in f.lower() for f in failures)

    categories_hit = sum([has_timeout, has_exit, has_pattern])
    if categories_hit > 1:
        return "multiple"
    if has_timeout:
        return "timeout"
    if has_exit:
        return "exit_code_mismatch"
    return "pattern_missing"


def _build_summary(
    step: ExecutionStep,
    result: ExecutionResult,
    failures: tuple[str, ...],
) -> str:
    """Build a concise human-readable summary of the diagnosis."""
    cmd = step.command
    failure_count = len(failures)
    first = failures[0] if failures else "unknown failure"
    if failure_count == 1:
        return f"step {cmd!r} failed: {first}"
    return f"step {cmd!r} failed with {failure_count} issues: {first} (and {failure_count - 1} more)"


# ---------------------------------------------------------------------------
# diagnose_plan()
# ---------------------------------------------------------------------------

def diagnose_plan(
    plan: ExecutionPlan,
    results: list[ExecutionResult],
    validation_results: list[ValidationResult],
) -> list[DiagnosisArtifact]:
    """Return one :class:`DiagnosisArtifact` for each failed step in *plan*.

    Steps whose validation passed are silently skipped — callers only see
    the failures that need attention.

    Parameters
    ----------
    plan:
        The execution plan whose steps are being diagnosed.
    results:
        One :class:`~src.execution_validator.ExecutionResult` per step.
    validation_results:
        One :class:`~src.execution_validator.ValidationResult` per step,
        in the same order as ``plan.steps`` and ``results``.

    Returns
    -------
    list[DiagnosisArtifact]
        Empty list when all steps passed.
    """
    artifacts: list[DiagnosisArtifact] = []
    for step, result, vr in zip(plan.steps, results, validation_results):
        artifact = diagnose_step(step, result, vr)
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts


# ---------------------------------------------------------------------------
# persist_diagnosis()
# ---------------------------------------------------------------------------

def persist_diagnosis(
    artifacts: list[DiagnosisArtifact],
    output_dir: Path,
) -> Path:
    """Write *artifacts* as ``diagnosis.json`` inside *output_dir*.

    Creates *output_dir* (and parents) if it does not yet exist.
    An empty artifact list writes an empty JSON array — callers can
    always call this function without checking first.

    Parameters
    ----------
    artifacts:
        Diagnosis artifacts to persist.
    output_dir:
        Directory to write the file into.

    Returns
    -------
    Path
        Absolute path to the written ``diagnosis.json`` file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "diagnosis.json"
    path.write_text(
        json.dumps([a.to_dict() for a in artifacts], indent=2),
        encoding="utf-8",
    )
    return path
