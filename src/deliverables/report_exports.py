"""Helpers for dashboard/report/tool-trace export coordination."""

from __future__ import annotations

import json
from typing import Any

from src.artifacts import tool_trace_payload, write_dashboard, write_html_report, write_pdf_report, write_portfolio
from src.pdf_report import render_simple_pdf
from src.portfolio import build_portfolio, render_portfolio_html
from src.reporting import render_html_report as render_html_report_fn


def write_reporting_artifacts(researcher: Any) -> None:
    """Write reporting-oriented artifacts for a completed run."""
    write_dashboard(
        researcher.output_dir,
        config=researcher.config,
        best_score=researcher.best_score,
        iteration=researcher.iteration,
        explored_dimensions=researcher.explored_dimensions,
        retry_summary=researcher._retry_summary,
        tool_loop_summary=researcher._tool_loop_summary,
    )
    payload = tool_trace_payload(tool_trace=researcher._tool_trace)
    researcher.tool_trace_path.parent.mkdir(parents=True, exist_ok=True)
    researcher.tool_trace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_html_report(researcher.output_dir, config=researcher.config, render_fn=render_html_report_fn)
    write_pdf_report(
        researcher.output_dir,
        config=researcher.config,
        best_score=researcher.best_score,
        iteration=researcher.iteration,
        explored_dimensions=researcher.explored_dimensions,
        render_pdf_fn=render_simple_pdf,
    )
    write_portfolio(researcher.output_dir, build_portfolio, render_portfolio_html)
