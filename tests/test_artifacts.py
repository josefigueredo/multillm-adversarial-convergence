"""Direct tests for artifact payload helpers."""

from pathlib import Path

from src.artifacts import (
    dashboard_payload,
    evaluation_payload,
    load_json_if_exists,
    metrics_payload,
    pdf_run_summary_text,
    should_write_evaluation,
    tool_trace_payload,
)
from src.config import EvaluationConfig, ExecutionConfig, ResearchConfig, ScoringConfig


def test_load_json_if_exists(tmp_path: Path):
    path = tmp_path / "payload.json"
    assert load_json_if_exists(path, {"ok": False}) == {"ok": False}
    path.write_text('{"ok": true}', encoding="utf-8")
    assert load_json_if_exists(path, {}) == {"ok": True}


def test_metrics_evaluation_and_dashboard_payloads():
    metrics = metrics_payload(
        benchmark_id="bench-1",
        run_status="completed",
        iteration=2,
        best_score=88.0,
        explored_dimensions=["DX"],
        discovered_dimensions=["Tooling"],
        total_cost=1.25,
        total_input_tokens=100,
        total_output_tokens=20,
        per_backend_costs={"claude-cli": 1.25},
        per_backend_tokens={"claude-cli": {"input": 100, "output": 20}},
        results=[{"iteration": "001"}],
        retry_summary={"total_retries": 2, "per_backend": {"litellm-api": 2}},
        tool_loop_summary={
            "runs": 2,
            "tool_calls": 3,
            "tool_failures": 1,
            "per_backend": {"codex-api": {"runs": 2}},
            "per_tool": {"echo": {"calls": 2, "failures": 1}},
        },
    )
    assert metrics["explored_dimensions_count"] == 1
    assert metrics["tool_loop_summary"]["tool_calls"] == 3
    assert metrics["tool_loop_summary"]["per_tool"]["echo"]["calls"] == 2
    assert metrics["retry_summary"]["total_retries"] == 2

    evaluation = evaluation_payload(
        benchmark_id="bench-1",
        baseline_exists=True,
        claims=[{"scope": "synthesis"}, {"scope": "baseline"}],
        citations=[{"scope": "synthesis"}, {"scope": "baseline"}],
        evidence_quality={"average_evidence_quality_score": 0.7},
        rubric={"grade": "good"},
        benchmark_summary={"all_expectations_satisfied": True},
        reference_comparison={"compared_runs_count": 1},
        semantic_review={"grade": "good"},
        semantic_calibration={"grade": "reasonable"},
    )
    assert evaluation["baseline_generated"] is True
    assert evaluation["summary"]["reference_runs_compared"] == 1

    dashboard = dashboard_payload(
        topic="Topic",
        goal="Goal",
        benchmark_id="bench-1",
        current_strategy="single",
        best_score=88.0,
        iteration=2,
        explored_dimensions=["DX"],
        rubric={"grade": "good", "overall_score": 0.8},
        evidence_quality={"average_evidence_quality_score": 0.7},
        comparison={"compared_runs_count": 1, "summary": {"consistency_level": "medium"}},
        evaluation={"summary": {"benchmark_expectations_satisfied": True}},
        strategy_summary={"current_strategy": "single"},
        semantic_calibration={"grade": "reasonable"},
        semantic_review={"grade": "good"},
        retry_summary={"total_retries": 2, "per_backend": {"litellm-api": 2}},
        tool_loop_summary={"runs": 2, "tool_calls": 3, "tool_failures": 1, "per_tool": {"echo": {"calls": 2}}},
    )
    assert dashboard["consistency_level"] == "medium"
    assert dashboard["rubric_grade"] == "good"
    assert dashboard["tool_loop_summary"]["runs"] == 2
    assert dashboard["tool_loop_summary"]["per_tool"]["echo"]["calls"] == 2
    assert dashboard["retry_summary"]["total_retries"] == 2
    assert dashboard["tool_usage_summary"]["top_tools"][0]["name"] == "echo"
    assert dashboard["tool_usage_summary"]["failure_hotspots"] == []

    trace = tool_trace_payload(
        tool_trace=[
            {
                "backend": "codex-api",
                "turn": 1,
                "tool_name": "echo",
                "call_id": "call_123",
                "status": "success",
            }
        ]
    )
    assert trace["entries_count"] == 1
    assert trace["redaction_policy"]["sensitive_values"] == "redacted"


def test_pdf_summary_and_should_write_evaluation():
    text = pdf_run_summary_text(
        topic="Python",
        goal="Compare options",
        strategy="single",
        best_score=88.0,
        iteration=2,
        explored_dimensions=["DX"],
        metrics={
            "iterations": 2,
            "tool_loop_summary": {
                "runs": 2,
                "tool_calls": 3,
                "tool_failures": 1,
                "per_tool": {"echo": {"calls": 2, "failures": 1}},
            },
            "retry_summary": {"total_retries": 2, "per_backend": {"litellm-api": 2}},
        },
        rubric={"grade": "good"},
        evidence_quality={"average_evidence_quality_score": 0.7},
    )
    assert "Topic: Python" in text
    assert "Rubric grade: good" in text
    assert "Tool loops: 2 runs / 3 calls / 1 failures" in text
    assert "API retries: 2" in text

    cfg = ResearchConfig(
        topic="x",
        goal="y",
        dimensions=("a",),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )
    assert should_write_evaluation(cfg) is False
    cfg = ResearchConfig(
        topic="x",
        goal="y",
        dimensions=("a",),
        evaluation=EvaluationConfig(run_baselines=True),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )
    assert should_write_evaluation(cfg) is True
