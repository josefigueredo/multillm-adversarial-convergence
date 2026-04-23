"""Direct tests for artifact payload helpers."""

from pathlib import Path

from src.artifacts import (
    certainty_pdf_text,
    dashboard_payload,
    evaluation_payload,
    load_json_if_exists,
    metrics_payload,
    pdf_run_summary_text,
    prompt_snapshot_payload,
    rerun_script_text,
    should_write_evaluation,
    tool_trace_payload,
)
from src.config import EvaluationConfig, ExecutionConfig, ResearchConfig, ScoringConfig
from src.config import OutputStyleOverrides, ReportingConfig


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
        retry_summary={
            "total_retries": 2,
            "per_backend": {"litellm-api": 2},
            "per_category": {"rate_limit": 2},
            "per_backend_category": {"litellm-api": {"rate_limit": 2}},
        },
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
    assert metrics["retry_summary"]["per_category"]["rate_limit"] == 2

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
        output_style="paper",
        output_style_label="Paper Style",
        active_style_overrides=["include methodology section"],
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
        certainty_summary={"conclusions_count": 2, "certainty_counts": {"high": 1, "moderate": 1}},
        search_log_summary={"queries_count": 2, "sources_considered": 5},
        screening_log_summary={"sources_screened": 5, "included_count": 3, "excluded_count": 2},
        retry_summary={
            "total_retries": 2,
            "per_backend": {"litellm-api": 2},
            "per_category": {"rate_limit": 2},
            "per_backend_category": {"litellm-api": {"rate_limit": 2}},
        },
        tool_loop_summary={"runs": 2, "tool_calls": 3, "tool_failures": 1, "per_tool": {"echo": {"calls": 2}}},
    )
    assert dashboard["consistency_level"] == "medium"
    assert dashboard["output_style"] == "paper"
    assert dashboard["output_style_label"] == "Paper Style"
    assert dashboard["active_style_overrides"] == ["include methodology section"]
    assert dashboard["rubric_grade"] == "good"
    assert dashboard["tool_loop_summary"]["runs"] == 2
    assert dashboard["tool_loop_summary"]["per_tool"]["echo"]["calls"] == 2
    assert dashboard["retry_summary"]["total_retries"] == 2
    assert dashboard["retry_insights"]["most_unstable_backend"]["backend"] == "litellm-api"
    assert dashboard["retry_insights"]["top_retry_categories"][0]["category"] == "rate_limit"
    assert dashboard["certainty_summary"]["conclusions_count"] == 2
    assert dashboard["search_log_summary"]["sources_considered"] == 5
    assert dashboard["screening_log_summary"]["included_count"] == 3
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
            },
            {
                "backend": "codex-api",
                "turn": 2,
                "tool_name": "explode",
                "call_id": "call_456",
                "status": "error",
                "provider_code": "tool_handler_failed",
            }
        ]
    )
    assert trace["entries_count"] == 2
    assert trace["redaction_policy"]["sensitive_values"] == "redacted"
    assert trace["summary"]["status_counts"]["error"] == 1
    assert trace["summary"]["top_failure_codes"][0]["provider_code"] == "tool_handler_failed"


def test_pdf_summary_and_should_write_evaluation():
    text = pdf_run_summary_text(
        topic="Python",
        goal="Compare options",
        strategy="single",
        output_style="decision_memo",
        output_style_label="Decision Memo",
        active_style_overrides=["decision-only recommendations"],
        best_score=88.0,
        iteration=2,
        explored_dimensions=["DX"],
        metrics={
            "iterations": 2,
            "certainty_summary": {
                "conclusions_count": 2,
                "certainty_counts": {"high": 1, "moderate": 1},
                "high_certainty_recommendation_count": 1,
            },
            "tool_loop_summary": {
                "runs": 2,
                "tool_calls": 3,
                "tool_failures": 1,
                "per_tool": {"echo": {"calls": 2, "failures": 1}},
            },
            "retry_summary": {
                "total_retries": 2,
                "per_backend": {"litellm-api": 2},
                "per_category": {"rate_limit": 2},
                "per_backend_category": {"litellm-api": {"rate_limit": 2}},
            },
        },
        rubric={"grade": "good"},
        evidence_quality={"average_evidence_quality_score": 0.7},
    )
    assert "Topic: Python" in text
    assert "Rubric grade: good" in text
    assert "Output style: decision_memo (Decision Memo)" in text
    assert "Style overrides: decision-only recommendations" in text
    assert "Certainty: 2 conclusions / top band high / high-certainty recommendations 1" in text
    assert "Tool loops: 2 runs / 3 calls / 1 failures" in text
    assert "API retries: 2" in text

    certainty_text = certainty_pdf_text(
        {
            "summary": {
                "conclusions_count": 2,
                "certainty_counts": {"high": 1, "moderate": 1},
                "high_certainty_recommendation_count": 1,
            },
            "conclusions": [
                {
                    "dimension": "DX",
                    "certainty": "high",
                    "factors": {
                        "risk_of_bias": {"level": "not_serious", "reason": "Average evidence quality score was 0.91."},
                        "inconsistency": {"level": "not_serious", "reason": "0 contradiction(s) were detected."},
                    },
                }
            ],
        }
    )
    assert "Conclusions: 2" in certainty_text
    assert "DX: high" in certainty_text
    assert "risk_of_bias: not_serious" in certainty_text

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


def test_write_pdf_report_uses_style_aware_title_and_sections(tmp_path: Path):
    from src.artifacts import write_pdf_report
    from src.config import ReportingConfig

    captured: dict[str, object] = {}

    def fake_render_pdf(title: str, sections: list[tuple[str, str]]) -> bytes:
        captured["title"] = title
        captured["sections"] = sections
        return b"%PDF-FAKE"

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "methods.md").write_text("# Methods", encoding="utf-8")
    (output_dir / "synthesis.md").write_text("# Draft", encoding="utf-8")

    cfg = ResearchConfig(
        topic="Topic",
        goal="Goal",
        dimensions=("a",),
        reporting=ReportingConfig(export_pdf=True, output_style="executive_brief"),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )

    write_pdf_report(
        output_dir,
        config=cfg,
        best_score=80.0,
        iteration=1,
        explored_dimensions=["DX"],
        render_pdf_fn=fake_render_pdf,
    )

    assert captured["title"] == "Autoresearch Report — Topic (Executive Brief)"
    section_names = [name for name, _ in captured["sections"]]
    assert "Approach" in section_names
    assert "Executive Brief" in section_names
    run_summary = dict(captured["sections"])["Run Summary"]
    assert "Output style: executive_brief (Executive Brief)" in run_summary


def test_prompt_snapshot_payload_and_rerun_script(tmp_path: Path):
    payload = prompt_snapshot_payload(
        prompts=[
            {
                "backend": "codex-api",
                "model": "gpt-5.4",
                "prompt": "Investigate Python packaging.",
            }
        ]
    )
    assert payload["entries_count"] == 1
    assert payload["entries"][0]["backend"] == "codex-api"
    assert payload["entries"][0]["prompt_sha256"]

    script = rerun_script_text(
        config_path=tmp_path / "config.yaml",
        output_dir=tmp_path / "run-output",
    )
    assert "autoresearch run" in script
    assert "--config" in script
    assert "--output" in script


def test_run_manifest_payload_includes_output_style_metadata(tmp_path: Path):
    from src.artifacts import run_manifest_payload

    cfg = ResearchConfig(
        topic="Topic",
        goal="Goal",
        dimensions=("a",),
        reporting=ReportingConfig(
            output_style="decision_memo",
            style_overrides=OutputStyleOverrides(
                include_executive_summary=False,
                recommendation_mode="decision_only",
            ),
        ),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(),
    )
    payload = run_manifest_payload(
        config=cfg,
        strategy_description="single",
        backends={},
        output_dir=tmp_path / "out",
        resume=False,
        config_path=None,
        run_status="initialized",
        run_started_at="2026-01-01T00:00:00Z",
        run_completed_at=None,
        package_version="1.0.0",
        git_commit="abc123",
        cli_version_resolver=lambda _: "1.0",
    )
    assert payload["reporting"]["output_style"] == "decision_memo"
    assert payload["reporting"]["output_style_label"] == "Decision Memo"
    assert payload["reporting"]["style_overrides"]["include_executive_summary"] is False
    assert payload["reporting"]["active_style_overrides"] == [
        "no executive summary",
        "decision-only recommendations",
    ]
