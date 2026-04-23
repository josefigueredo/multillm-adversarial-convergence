"""Tests for src.portfolio — multi-run portfolio aggregation."""

import json

from src.portfolio import build_portfolio, render_portfolio_html


def test_build_portfolio_collects_dashboards(tmp_path):
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    (run_a / "dashboard.json").write_text(
        json.dumps(
            {
                "topic": "Topic A",
                "benchmark_id": "bench-001",
                "current_strategy": "single",
                "best_score": 72.5,
                "rubric_grade": "good",
                "consistency_level": "medium",
                "certainty_summary": {
                    "conclusions_count": 2,
                    "certainty_counts": {"moderate": 2},
                    "high_certainty_recommendation_count": 0,
                },
                "retry_summary": {"total_retries": 1},
                "tool_loop_summary": {"tool_calls": 2, "tool_failures": 1},
            }
        ),
        encoding="utf-8",
    )
    (run_b / "dashboard.json").write_text(
        json.dumps(
            {
                "topic": "Topic B",
                "benchmark_id": "bench-002",
                "current_strategy": "ensemble",
                "best_score": 88.1,
                "rubric_grade": "strong",
                "consistency_level": "high",
                "certainty_summary": {
                    "conclusions_count": 3,
                    "certainty_counts": {"high": 2, "moderate": 1},
                    "high_certainty_recommendation_count": 1,
                },
                "retry_summary": {"total_retries": 3},
                "tool_loop_summary": {"tool_calls": 5, "tool_failures": 0},
            }
        ),
        encoding="utf-8",
    )

    portfolio = build_portfolio(tmp_path)
    assert portfolio["runs_count"] == 2
    assert portfolio["best_run"]["name"] == "run-b"
    assert portfolio["most_unstable_run"]["name"] == "run-b"
    assert set(portfolio["strategies"]) == {"single", "ensemble"}
    assert set(portfolio["benchmarks"]) == {"bench-001", "bench-002"}
    assert portfolio["total_retries"] == 4
    assert portfolio["total_tool_calls"] == 7
    assert portfolio["total_tool_failures"] == 1
    assert portfolio["total_certainty_conclusions"] == 5
    assert portfolio["certainty_counts"]["high"] == 2
    assert portfolio["best_certainty_run"]["name"] == "run-b"
    assert portfolio["runs"][0]["certainty_delta_from_best"] == -2
    assert portfolio["runs"][1]["certainty_delta_from_best"] == 0
    assert portfolio["total_high_certainty_recommendations"] == 1


def test_render_portfolio_html_renders_table():
    html = render_portfolio_html(
        "Portfolio",
        {
            "runs_count": 1,
            "strategies": ["ensemble"],
            "benchmarks": ["bench-001"],
            "best_run": {"name": "run-b", "best_score": 88.1},
            "best_certainty_run": {"name": "run-b", "high_certainty_conclusions": 2},
            "most_unstable_run": {"name": "run-b", "total_retries": 3},
            "total_retries": 3,
            "total_tool_calls": 5,
            "total_tool_failures": 1,
            "total_certainty_conclusions": 3,
            "certainty_counts": {"high": 2, "moderate": 1},
            "total_high_certainty_recommendations": 1,
            "runs": [
                {
                    "name": "run-b",
                    "topic": "Topic B",
                    "benchmark_id": "bench-001",
                    "current_strategy": "ensemble",
                    "best_score": 88.1,
                    "rubric_grade": "strong",
                    "consistency_level": "high",
                    "total_retries": 3,
                    "tool_calls": 5,
                    "tool_failures": 1,
                    "certainty_conclusions": 3,
                    "high_certainty_conclusions": 2,
                    "high_certainty_recommendations": 1,
                    "certainty_delta_from_best": 0,
                }
            ],
        },
    )
    assert "Portfolio" in html
    assert "run-b" in html
    assert "Topic B" in html
    assert "ensemble" in html
    assert "Total retries" in html
    assert "Tool calls" in html
    assert "High-certainty conclusions" in html
    assert "Certainty Δ vs best" in html
