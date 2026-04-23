"""Tests for src.reporting -- template-based HTML report rendering."""

from src.reporting import (
    _comparison_html,
    _certainty_html,
    _dashboard_html,
    _dimensions_html,
    _evaluation_html,
    _retry_html,
    _search_screening_html,
    _semantic_html,
    _semantic_review_html,
    _summary_cards_html,
    _tool_trace_html,
    _tool_usage_html,
    render_html_report,
)


def test_render_html_report_renders_core_sections_and_escapes():
    html = render_html_report(
        title="Report <Unsafe>",
        topic="Topic & Scope",
        goal="Goal > Outcome",
        manifest={
            "run": {"status": "completed", "started_at": "2026-04-10", "completed_at": "2026-04-10"},
            "strategy": {"name": "ensemble"},
        },
        metrics={
            "best_score": 91.2,
            "iterations": 3,
            "explored_dimensions_count": 2,
            "explored_dimensions": ["DX", "Security"],
            "total_cost_usd": 1.23,
        },
        evidence_quality={"average_evidence_quality_score": 0.82},
        rubric={"grade": "strong", "overall_score": 0.88},
        evaluation={"benchmark_id": "bench-001", "summary": {"rubric_grade": "strong"}},
        comparison={"compared_runs_count": 1, "summary": {"consistency_level": "high"}},
        semantic_calibration={"enabled": True, "grade": "reasonable", "calibrated_score": 0.81},
        semantic_review={"enabled": True, "grade": "good", "overall_score": 0.76, "judge_backend": "claude-cli"},
        certainty_tables={
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
                        "risk_of_bias": {"level": "not_serious"},
                        "inconsistency": {"level": "not_serious"},
                    },
                }
            ],
        },
        dashboard={
            "current_strategy": "ensemble",
            "certainty_summary": {
                "conclusions_count": 2,
                "certainty_counts": {"high": 1, "moderate": 1},
                "high_certainty_recommendation_count": 1,
            },
            "retry_summary": {
                "total_retries": 2,
                "per_backend": {"litellm-api": 2},
                "per_category": {"rate_limit": 2},
                "per_backend_category": {"litellm-api": {"rate_limit": 2}},
            },
            "retry_insights": {
                "most_unstable_backend": {"backend": "litellm-api", "retries": 2},
                "top_retry_categories": [{"category": "rate_limit", "count": 2}],
            },
            "search_log_summary": {"queries_count": 2, "sources_considered": 5},
            "screening_log_summary": {"sources_screened": 5, "included_count": 3, "excluded_count": 2},
            "tool_usage_summary": {
                "top_tools": [{"name": "echo", "calls": 2, "failures": 1}],
                "failure_hotspots": [{"backend": "codex-api", "tool_name": "echo", "failures": 1}],
            },
            "tool_trace_summary": {
                "entries_count": 3,
                "status_counts": {"success": 2, "error": 1},
                "top_failure_codes": [{"provider_code": "tool_handler_failed", "count": 1}],
            },
        },
        methods_text="# Method <1>\n\nSome **bold** text.",
        synthesis_text="Use <Python> & cite [sources](https://example.com).",
    )

    # Title and header escape HTML entities
    assert "Report &lt;Unsafe&gt;" in html
    assert "Topic &amp; Scope" in html
    assert "Goal &gt; Outcome" in html
    # Core sections present
    assert "Run Summary" in html
    assert "Semantic Calibration" in html
    assert "Semantic Judge Review" in html
    assert "Certainty Tables" in html
    assert "risk_of_bias" in html
    assert "API Retries" in html
    assert "Search &amp; Screening" in html
    assert "Dashboard Summary" in html
    assert "Tool Usage" in html
    assert "Tool Trace" in html
    assert "Consistency Comparison" in html
    # Markdown content embedded as JS string, not HTML-escaped in <pre>
    assert "marked.parse" in html
    assert "SYNTHESIS_RAW" in html
    assert "METHODS_RAW" in html
    # JSON content embedded as JS objects
    assert "EVIDENCE_QUALITY_DATA" in html
    assert "RUBRIC_DATA" in html
    assert "renderJsonTable" in html


def test_render_html_report_omits_optional_sections_when_empty():
    html = render_html_report(
        title="Plain",
        topic="Topic",
        goal="Goal",
        manifest={"run": {}, "strategy": {}},
        metrics={"explored_dimensions": []},
        evidence_quality={},
        rubric={},
        evaluation=None,
        comparison=None,
        semantic_calibration=None,
        semantic_review=None,
        certainty_tables=None,
        dashboard=None,
        methods_text="Methods",
        synthesis_text="Synthesis",
    )

    assert "Semantic Calibration" not in html
    assert "Dashboard Summary" not in html
    assert "API Retries" not in html
    assert "Search & Screening" not in html
    assert "Tool Usage" not in html
    assert "Tool Trace" not in html
    assert "Semantic Judge Review" not in html
    assert "Consistency Comparison" not in html
    assert "Evaluation" not in html
    assert "<li>(none)</li>" in html


def test_helper_html_sections_behave_as_expected():
    assert "Compared runs:" in _comparison_html({"compared_runs_count": 2, "summary": {"consistency_level": "medium"}})
    assert _comparison_html({"compared_runs_count": 0}) == ""
    assert "Dashboard Summary" in _dashboard_html({"foo": "bar"})
    assert _dashboard_html(None) == ""
    assert "Benchmark:" in _evaluation_html({"benchmark_id": "bench-1", "summary": {"rubric_grade": "good"}})
    assert _evaluation_html(None) == ""
    assert "Total retries:" in _retry_html(
        {
            "total_retries": 2,
            "per_backend": {"litellm-api": 2},
            "per_category": {"rate_limit": 2},
            "per_backend_category": {"litellm-api": {"rate_limit": 2}},
        },
        {
            "most_unstable_backend": {"backend": "litellm-api", "retries": 2},
            "top_retry_categories": [{"category": "rate_limit", "count": 2}],
        },
    )
    assert _retry_html({"total_retries": 0, "per_backend": {}}, {}) == ""
    assert "Included sources:" in _search_screening_html(
        {"queries_count": 2, "sources_considered": 5},
        {"sources_screened": 5, "included_count": 3, "excluded_count": 2},
    )
    assert _search_screening_html({}, {}) == ""
    assert "Calibrated score:" in _semantic_html({"enabled": True, "grade": "reasonable", "calibrated_score": 0.7})
    assert _semantic_html({"enabled": False}) == ""
    assert "Overall score:" in _semantic_review_html(
        {"enabled": True, "grade": "good", "overall_score": 0.74, "judge_backend": "claude-cli"}
    )
    assert _semantic_review_html({"enabled": False}) == ""
    assert "Top certainty band:" in _certainty_html(
        {
            "conclusions_count": 2,
            "certainty_counts": {"high": 1, "moderate": 1},
            "high_certainty_recommendation_count": 1,
        }
    )
    assert _certainty_html({"conclusions_count": 0, "certainty_counts": {}}) == ""
    assert "Top tools" in _tool_usage_html(
        {
            "top_tools": [{"name": "echo", "calls": 2, "failures": 1}],
            "failure_hotspots": [{"backend": "codex-api", "tool_name": "echo", "failures": 1}],
        }
    )
    assert _tool_usage_html(None) == ""
    assert "Failed calls:" in _tool_trace_html(
        {
            "entries_count": 3,
            "status_counts": {"success": 2, "error": 1},
            "top_failure_codes": [{"provider_code": "tool_handler_failed", "count": 1}],
        }
    )
    assert _tool_trace_html(None) == ""


def test_json_sections_use_renderJsonTable():
    """JSON sections should use JS-based rendering, not <pre> with raw text."""
    html = _dashboard_html({"current_strategy": "ensemble", "best_score": 80.0})
    assert "renderJsonTable" in html
    assert "json-section-" in html
    # Should NOT have _pretty_json_like output
    assert "'current_strategy'" not in html


def test_helper_formatters_cover_lists_and_cards():
    cards = _summary_cards_html({"A": 1, "B": 2})
    assert cards.count('class="card"') == 2
    assert "A" in cards and "2" in cards

    dims = _dimensions_html(["One", "Two"])
    assert "<li>One</li>" in dims
    assert "<li>Two</li>" in dims
    assert _dimensions_html([]) == "<li>(none)</li>"
