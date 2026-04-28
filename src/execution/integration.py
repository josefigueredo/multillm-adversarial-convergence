"""Execution subsystem integration — MM10 Step 5.

Adapter layer that bridges the implement/research domain to the execution
plan/validator/diagnosis/repair subsystem introduced in MM10.

Each adapter function is pure and injected — no global state, no I/O
except through the functions that explicitly request it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.execution.diagnosis import DiagnosisArtifact, diagnose_plan
from src.execution.plan import ExecutionPlan, ExecutionStep, TargetContext
from src.execution.validator import ExecutionResult, validate_plan

if TYPE_CHECKING:
    from .implement_loop import ImplementConfig, TaskState


# ---------------------------------------------------------------------------
# Implement-domain adapters
# ---------------------------------------------------------------------------

def build_implement_execution_plan(config: "ImplementConfig") -> ExecutionPlan:
    """Build an :class:`~src.execution_plan.ExecutionPlan` from an implement config.

    The plan has a single step that names the implement task.  This gives the
    validator/diagnosis layer a concrete handle for the run.
    """
    step = ExecutionStep(
        command=f"implement: {config.task_description}",
        expected_exit_code=0,
    )
    target = TargetContext(working_dir=config.target.path.resolve())
    return ExecutionPlan(steps=(step,), target=target)


def result_from_implement_state(state: "TaskState") -> ExecutionResult:
    """Convert a :class:`~src.implement_loop.TaskState` to an :class:`~src.execution_validator.ExecutionResult`.

    A state with boundary violations is a failed execution (exit code 1);
    a clean state is a passing execution (exit code 0).
    """
    if state.boundary_violations:
        return ExecutionResult(
            exit_code=1,
            stdout=f"patches={len(state.patches)}",
            stderr="; ".join(state.boundary_violations),
        )
    return ExecutionResult(
        exit_code=0,
        stdout=f"patches={len(state.patches)} critiques={len(state.critiques)}",
        stderr="",
    )


def diagnose_implement_failure(
    state: "TaskState",
    config: "ImplementConfig",
) -> list[DiagnosisArtifact]:
    """Produce :class:`~src.execution_diagnosis.DiagnosisArtifact` objects for a failed implement run.

    Returns an empty list when the state carries no failures (clean run).
    """
    plan = build_implement_execution_plan(config)
    result = result_from_implement_state(state)
    vrs = validate_plan(plan, [result])
    return diagnose_plan(plan, [result], vrs)


# ---------------------------------------------------------------------------
# Research-domain adapters
# ---------------------------------------------------------------------------

def build_research_execution_plan(
    dimension: str,
    questions: list[str],
    working_dir: Path,
) -> ExecutionPlan:
    """Build an :class:`~src.execution_plan.ExecutionPlan` for a research execution step.

    The plan always has a single step regardless of the number of questions.
    """
    q_summary = "; ".join(questions[:3]) if questions else "explore broadly"
    step = ExecutionStep(
        command=f"research: {dimension} — {q_summary}",
        expected_exit_code=0,
    )
    target = TargetContext(working_dir=working_dir.resolve())
    return ExecutionPlan(steps=(step,), target=target)


def result_from_findings(findings: str) -> ExecutionResult:
    """Convert a research findings string to an :class:`~src.execution_validator.ExecutionResult`.

    Non-empty findings are a passing result; empty findings are a failure.
    """
    if findings:
        return ExecutionResult(exit_code=0, stdout=findings, stderr="")
    return ExecutionResult(
        exit_code=1,
        stdout="",
        stderr="No findings returned by research agent",
    )


def diagnose_research_failure(dimension: str, working_dir: Path) -> DiagnosisArtifact:
    """Produce a :class:`~src.execution_diagnosis.DiagnosisArtifact` for a failed research step.

    Always returns exactly one artifact (the plan has one step and it failed).
    """
    plan = build_research_execution_plan(dimension, [], working_dir)
    result = result_from_findings("")
    vrs = validate_plan(plan, [result])
    artifacts = diagnose_plan(plan, [result], vrs)
    return artifacts[0]
