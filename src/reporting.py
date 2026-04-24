"""HTML reporting helpers for autoresearch run artifacts.

Renders a standalone HTML report using client-side marked.js for markdown
and inline JS for collapsible JSON tables.  Raw content is embedded as
JSON-encoded JS variables, not HTML-escaped ``<pre>`` blocks.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from string import Template
from typing import Any

from .output_style import (
    build_output_style_presentation,
    build_output_style_report_policy,
    build_output_style_theme,
)


_TEMPLATES_DIR = Path(__file__).with_name("templates")
_TEMPLATE_PATH = _TEMPLATES_DIR / "report.html.tmpl"
_MAIN_CSS_PATH = _TEMPLATES_DIR / "report.css"
_PRINT_CSS_PATH = _TEMPLATES_DIR / "report_print.css"
_PARTIALS_DIR = _TEMPLATES_DIR / "partials"
_HEADER_TEMPLATE_PATH = _PARTIALS_DIR / "report_header.tmpl"
_JSON_SECTION_TEMPLATE_PATH = _PARTIALS_DIR / "json_section.tmpl"

_SECTION_COUNTER = 0


def render_html_report(
    *,
    title: str,
    output_style: str,
    topic: str,
    goal: str,
    manifest: dict[str, Any],
    metrics: dict[str, Any],
    evidence_quality: dict[str, Any],
    rubric: dict[str, Any],
    evaluation: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
    semantic_calibration: dict[str, Any] | None,
    semantic_review: dict[str, Any] | None,
    certainty_tables: dict[str, Any] | None,
    dashboard: dict[str, Any] | None,
    methods_text: str,
    synthesis_text: str,
) -> str:
    """Render a standalone HTML report from a filesystem template."""
    global _SECTION_COUNTER
    _SECTION_COUNTER = 0
    presentation = build_output_style_presentation(output_style)
    policy = build_output_style_report_policy(output_style)
    theme = build_output_style_theme(output_style)

    run = manifest.get("run", {})
    strategy = manifest.get("strategy", {})
    summary_cards = {
        "Best score": metrics.get("best_score", 0.0),
        "Iterations": metrics.get("iterations", 0),
        "Rubric grade": rubric.get("grade", "insufficient"),
        "Evidence quality": evidence_quality.get("average_evidence_quality_score", 0.0),
        "Explored dimensions": metrics.get("explored_dimensions_count", len(metrics.get("explored_dimensions", []))),
        "Total cost (USD)": metrics.get("total_cost_usd", 0.0),
    }

    template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    header_template = Template(_HEADER_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return template.safe_substitute(
        title=escape(title),
        main_css=_MAIN_CSS_PATH.read_text(encoding="utf-8").strip(),
        style_css=theme["style_css"],
        print_css=_PRINT_CSS_PATH.read_text(encoding="utf-8").strip(),
        report_class=escape(theme["report_class"]),
        header_html=header_template.safe_substitute(
            title=escape(title),
            style_label=escape(presentation["style_label"]),
            topic=escape(topic),
            goal=escape(goal),
            strategy_name=escape(str(strategy.get("name", ""))),
            run_status=escape(str(run.get("status", ""))),
            started_at=escape(str(run.get("started_at", ""))),
            completed_at=escape(str(run.get("completed_at", ""))),
        ),
        topic=escape(topic),
        goal=escape(goal),
        style_label=escape(presentation["style_label"]),
        strategy_name=escape(str(strategy.get("name", ""))),
        run_status=escape(str(run.get("status", ""))),
        started_at=escape(str(run.get("started_at", ""))),
        completed_at=escape(str(run.get("completed_at", ""))),
        run_summary_html=_section_html("Run Summary", f'<div class="grid">{_summary_cards_html(summary_cards)}</div>')
        if policy["show_run_summary"]
        else "",
        dimensions_section_html=_section_html("Dimensions Explored", f'<ul>{_dimensions_html(metrics.get("explored_dimensions", []))}</ul>')
        if policy["show_dimensions"]
        else "",
        style_html=_style_html(
            output_style=output_style,
            style_label=presentation["style_label"],
            active_overrides=(dashboard or {}).get("active_style_overrides"),
        )
        if policy["show_style_section"]
        else "",
        methods_section_html=_section_html(
            presentation["methods_heading"],
            '<div class="markdown-body" id="methods-content"></div>',
        )
        if policy["show_methods"]
        else "",
        synthesis_section_html=_section_html(
            presentation["synthesis_heading"],
            '<div class="markdown-body" id="synthesis-content"></div>',
        )
        if policy["show_synthesis"]
        else "",
        evidence_quality_html=_section_html(
            "Evidence Quality",
            '<div class="json-view" id="evidence-quality-content"></div>',
        )
        if policy["show_evidence_quality"]
        else "",
        rubric_html=_section_html(
            "Rubric",
            '<div class="json-view" id="rubric-content"></div>',
        )
        if policy["show_rubric"]
        else "",
        methods_heading=escape(presentation["methods_heading"]),
        synthesis_heading=escape(presentation["synthesis_heading"]),
        methods_json=json.dumps(methods_text),
        synthesis_json=json.dumps(synthesis_text),
        evidence_quality_json=json.dumps(evidence_quality),
        rubric_json=json.dumps(rubric),
        semantic_html=_semantic_html(semantic_calibration) if policy["show_semantic"] else "",
        semantic_review_html=_semantic_review_html(semantic_review) if policy["show_semantic_review"] else "",
        certainty_html=_certainty_html((dashboard or {}).get("certainty_summary"), certainty_tables)
        if policy["show_certainty"]
        else "",
        search_screening_html=_search_screening_html(
            (dashboard or {}).get("search_log_summary"),
            (dashboard or {}).get("screening_log_summary"),
        )
        if policy["show_search_screening"]
        else "",
        retry_html=_retry_html(
            (dashboard or {}).get("retry_summary"),
            (dashboard or {}).get("retry_insights"),
        )
        if policy["show_retry"]
        else "",
        tool_usage_html=_tool_usage_html((dashboard or {}).get("tool_usage_summary")) if policy["show_tool_usage"] else "",
        tool_trace_html=_tool_trace_html((dashboard or {}).get("tool_trace_summary")) if policy["show_tool_trace"] else "",
        dashboard_html=_dashboard_html(dashboard) if policy["show_dashboard"] else "",
        evaluation_html=_evaluation_html(evaluation) if policy["show_evaluation"] else "",
        comparison_html=_comparison_html(comparison) if policy["show_comparison"] else "",
    )


def _section_html(title: str, body_html: str) -> str:
    return f"<section>\n    <h2>{escape(title)}</h2>\n    {body_html}\n  </section>"


def _summary_cards_html(summary_cards: dict[str, Any]) -> str:
    return "".join(
        f'<div class="card"><div class="label">{escape(str(label))}</div><div class="value">{escape(str(value))}</div></div>'
        for label, value in summary_cards.items()
    )


def _dimensions_html(dimensions: list[Any]) -> str:
    return "".join(f"<li>{escape(str(dim))}</li>" for dim in dimensions) or "<li>(none)</li>"


def _style_html(
    *,
    output_style: str,
    style_label: str,
    active_overrides: list[str] | None,
) -> str:
    overrides = active_overrides or []
    payload = {
        "output_style": output_style,
        "style_label": style_label,
        "active_overrides": overrides,
        "overrides_count": len(overrides),
    }
    return _json_section_html(
        "Output Style",
        payload,
        [
            ("Style", style_label),
            ("Profile key", output_style),
            ("Active overrides", ", ".join(overrides) or "none"),
        ],
    )


def _evaluation_html(evaluation: dict[str, Any] | None) -> str:
    if not evaluation:
        return ""
    return _json_section_html(
        "Evaluation",
        evaluation,
        [
            ("Benchmark", evaluation.get("benchmark_id", "")),
            ("Rubric grade", evaluation.get("summary", {}).get("rubric_grade", "")),
        ],
    )


def _comparison_html(comparison: dict[str, Any] | None) -> str:
    if not comparison or not comparison.get("compared_runs_count", 0):
        return ""
    return _json_section_html(
        "Consistency Comparison",
        comparison,
        [
            ("Compared runs", comparison.get("compared_runs_count", 0)),
            ("Consistency level", comparison.get("summary", {}).get("consistency_level", "")),
        ],
    )


def _dashboard_html(dashboard: dict[str, Any] | None) -> str:
    if not dashboard:
        return ""
    return _json_section_html("Dashboard Summary", dashboard)


def _tool_usage_html(tool_usage: dict[str, Any] | None) -> str:
    if not tool_usage:
        return ""
    top_tools = tool_usage.get("top_tools", [])
    failure_hotspots = tool_usage.get("failure_hotspots", [])
    if not top_tools and not failure_hotspots:
        return ""
    return _json_section_html(
        "Tool Usage",
        tool_usage,
        [
            ("Top tools", ", ".join(str(item.get("name", "")) for item in top_tools if isinstance(item, dict))),
            ("Failure hotspots", len(failure_hotspots)),
        ],
    )


def _tool_trace_html(tool_trace_summary: dict[str, Any] | None) -> str:
    if not tool_trace_summary:
        return ""
    entries_count = int(tool_trace_summary.get("entries_count", 0) or 0)
    if entries_count <= 0:
        return ""
    status_counts = tool_trace_summary.get("status_counts", {})
    failed_calls = int(status_counts.get("error", 0) or 0) if isinstance(status_counts, dict) else 0
    top_failure_codes = tool_trace_summary.get("top_failure_codes", [])
    return _json_section_html(
        "Tool Trace",
        tool_trace_summary,
        [
            ("Trace entries", entries_count),
            ("Failed calls", failed_calls),
            (
                "Top failure code",
                top_failure_codes[0].get("provider_code", "")
                if top_failure_codes and isinstance(top_failure_codes[0], dict)
                else "",
            ),
        ],
    )


def _search_screening_html(
    search_log_summary: dict[str, Any] | None,
    screening_log_summary: dict[str, Any] | None,
) -> str:
    search_log_summary = search_log_summary or {}
    screening_log_summary = screening_log_summary or {}
    considered = int(search_log_summary.get("sources_considered", 0) or 0)
    screened = int(screening_log_summary.get("sources_screened", 0) or 0)
    if considered <= 0 and screened <= 0:
        return ""
    return _json_section_html(
        "Search & Screening",
        {
            "search_log_summary": search_log_summary,
            "screening_log_summary": screening_log_summary,
        },
        [
            ("Queries", int(search_log_summary.get("queries_count", 0) or 0)),
            ("Sources considered", considered),
            ("Included sources", int(screening_log_summary.get("included_count", 0) or 0)),
            ("Excluded sources", int(screening_log_summary.get("excluded_count", 0) or 0)),
        ],
    )


def _retry_html(retry_summary: dict[str, Any] | None, retry_insights: dict[str, Any] | None = None) -> str:
    if not retry_summary:
        return ""
    total_retries = int(retry_summary.get("total_retries", 0) or 0)
    if total_retries <= 0:
        return ""
    retry_insights = retry_insights or {}
    most_unstable = retry_insights.get("most_unstable_backend", {}) if isinstance(retry_insights, dict) else {}
    top_categories = retry_insights.get("top_retry_categories", []) if isinstance(retry_insights, dict) else []
    return _json_section_html(
        "API Retries",
        {
            "summary": retry_summary,
            "insights": retry_insights,
        },
        [
            ("Total retries", total_retries),
            ("Backends affected", len(retry_summary.get("per_backend", {}) or {})),
            ("Most unstable backend", most_unstable.get("backend", "")),
            (
                "Top retry category",
                top_categories[0].get("category", "") if top_categories and isinstance(top_categories[0], dict) else "",
            ),
        ],
    )


def _semantic_html(semantic_calibration: dict[str, Any] | None) -> str:
    if not semantic_calibration or not semantic_calibration.get("enabled", False):
        return ""
    return _json_section_html(
        "Semantic Calibration",
        semantic_calibration,
        [
            ("Grade", semantic_calibration.get("grade", "")),
            ("Calibrated score", semantic_calibration.get("calibrated_score", "")),
        ],
    )


def _semantic_review_html(semantic_review: dict[str, Any] | None) -> str:
    if not semantic_review or not semantic_review.get("enabled", False):
        return ""
    return _json_section_html(
        "Semantic Judge Review",
        semantic_review,
        [
            ("Grade", semantic_review.get("grade", "")),
            ("Overall score", semantic_review.get("overall_score", "")),
            ("Judge backend", semantic_review.get("judge_backend", "")),
        ],
    )


def _certainty_html(
    certainty_summary: dict[str, Any] | None,
    certainty_tables: dict[str, Any] | None = None,
) -> str:
    if not certainty_summary:
        return ""
    conclusions_count = int(certainty_summary.get("conclusions_count", 0) or 0)
    certainty_counts = certainty_summary.get("certainty_counts", {})
    if conclusions_count <= 0:
        return ""
    top_band = ""
    if isinstance(certainty_counts, dict) and certainty_counts:
        top_band = max(certainty_counts.items(), key=lambda item: int(item[1] or 0))[0]
    payload: dict[str, Any] = certainty_summary
    if certainty_tables:
        payload = {
            "summary": certainty_summary,
            "conclusions": certainty_tables.get("conclusions", []),
        }
    return _json_section_html(
        "Certainty Tables",
        payload,
        [
            ("Conclusions", conclusions_count),
            ("Top certainty band", top_band),
            ("High-certainty conclusions", int((certainty_counts or {}).get("high", 0) or 0)),
            (
                "High-certainty recommendations",
                int(certainty_summary.get("high_certainty_recommendation_count", 0) or 0),
            ),
        ],
    )


def _json_section_html(
    heading: str,
    payload: dict[str, Any],
    meta_rows: list[tuple[str, Any]] | None = None,
) -> str:
    """Render a JSON section with collapsible table via the shared partial."""
    global _SECTION_COUNTER
    _SECTION_COUNTER += 1
    section_id = f"json-section-{_SECTION_COUNTER}"

    template = Template(_JSON_SECTION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    meta_html = "".join(
        f'<p><strong>{escape(str(label))}:</strong> {escape(str(value))}</p>'
        for label, value in (meta_rows or [])
        if value not in ("", None)
    )
    return template.safe_substitute(
        heading=escape(heading),
        meta_html=meta_html,
        section_id=section_id,
        body_json=json.dumps(payload),
    )
