"""Aggregate multiple run dashboards into a portfolio view."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from string import Template
from typing import Any


_PORTFOLIO_TEMPLATE_PATH = Path(__file__).with_name("templates") / "portfolio.html.tmpl"


@dataclass(frozen=True)
class PortfolioRun:
    name: str
    path: str
    topic: str
    benchmark_id: str
    current_strategy: str
    best_score: float
    rubric_grade: str
    consistency_level: str
    certainty_conclusions: int
    high_certainty_conclusions: int
    total_retries: int
    tool_calls: int
    tool_failures: int


def build_portfolio(output_root: Path) -> dict[str, Any]:
    """Build a portfolio summary from sibling run directories."""
    runs: list[PortfolioRun] = []
    for child in sorted(output_root.iterdir()):
        if not child.is_dir():
            continue
        dashboard_path = child / "dashboard.json"
        if not dashboard_path.exists():
            continue
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        runs.append(
            PortfolioRun(
                name=child.name,
                path=str(child),
                topic=str(dashboard.get("topic", "")),
                benchmark_id=str(dashboard.get("benchmark_id", "")),
                current_strategy=str(dashboard.get("current_strategy", "")),
                best_score=float(dashboard.get("best_score", 0.0)),
                rubric_grade=str(dashboard.get("rubric_grade", "insufficient")),
                consistency_level=str(dashboard.get("consistency_level", "not_available")),
                certainty_conclusions=int(dashboard.get("certainty_summary", {}).get("conclusions_count", 0) or 0),
                high_certainty_conclusions=int(
                    dashboard.get("certainty_summary", {}).get("certainty_counts", {}).get("high", 0) or 0
                ),
                total_retries=int(dashboard.get("retry_summary", {}).get("total_retries", 0) or 0),
                tool_calls=int(dashboard.get("tool_loop_summary", {}).get("tool_calls", 0) or 0),
                tool_failures=int(dashboard.get("tool_loop_summary", {}).get("tool_failures", 0) or 0),
            )
        )

    strategies = sorted({run.current_strategy for run in runs if run.current_strategy})
    benchmarks = sorted({run.benchmark_id for run in runs if run.benchmark_id})
    best_run = max(runs, key=lambda run: run.best_score) if runs else None
    best_certainty_run = max(runs, key=lambda run: run.high_certainty_conclusions) if runs else None
    most_unstable_run = max(runs, key=lambda run: run.total_retries) if runs else None
    certainty_counts: dict[str, int] = {}
    for run in runs:
        dashboard_path = Path(run.path) / "dashboard.json"
        if not dashboard_path.exists():
            continue
        dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
        run_counts = dashboard.get("certainty_summary", {}).get("certainty_counts", {})
        if isinstance(run_counts, dict):
            for label, count in run_counts.items():
                certainty_counts[str(label)] = certainty_counts.get(str(label), 0) + int(count or 0)
    return {
        "runs_count": len(runs),
        "strategies": strategies,
        "benchmarks": benchmarks,
        "best_run": best_run.__dict__ if best_run else {},
        "best_certainty_run": (
            best_certainty_run.__dict__
            if best_certainty_run and best_certainty_run.high_certainty_conclusions > 0
            else {}
        ),
        "most_unstable_run": most_unstable_run.__dict__ if most_unstable_run and most_unstable_run.total_retries > 0 else {},
        "total_certainty_conclusions": sum(run.certainty_conclusions for run in runs),
        "certainty_counts": certainty_counts,
        "total_retries": sum(run.total_retries for run in runs),
        "total_tool_calls": sum(run.tool_calls for run in runs),
        "total_tool_failures": sum(run.tool_failures for run in runs),
        "runs": [run.__dict__ for run in runs],
    }


def render_portfolio_html(title: str, portfolio: dict[str, Any]) -> str:
    """Render a standalone HTML portfolio page."""
    template = Template(_PORTFOLIO_TEMPLATE_PATH.read_text(encoding="utf-8"))
    runs_html = "".join(
        (
            "<tr>"
            f"<td>{escape(str(run['name']))}</td>"
            f"<td>{escape(str(run['topic']))}</td>"
            f"<td>{escape(str(run['benchmark_id']))}</td>"
            f"<td>{escape(str(run['current_strategy']))}</td>"
            f"<td>{escape(str(run['best_score']))}</td>"
            f"<td>{escape(str(run['rubric_grade']))}</td>"
            f"<td>{escape(str(run['consistency_level']))}</td>"
            f"<td>{escape(str(run.get('certainty_conclusions', 0)))}</td>"
            f"<td>{escape(str(run.get('high_certainty_conclusions', 0)))}</td>"
            f"<td>{escape(str(run.get('total_retries', 0)))}</td>"
            f"<td>{escape(str(run.get('tool_calls', 0)))}</td>"
            f"<td>{escape(str(run.get('tool_failures', 0)))}</td>"
            "</tr>"
        )
        for run in portfolio.get("runs", [])
    )
    if not runs_html:
        runs_html = '<tr><td colspan="12">(no runs)</td></tr>'

    best_run = portfolio.get("best_run", {})
    best_certainty_run = portfolio.get("best_certainty_run", {})
    most_unstable_run = portfolio.get("most_unstable_run", {})
    return template.safe_substitute(
        title=escape(title),
        runs_count=escape(str(portfolio.get("runs_count", 0))),
        strategies=escape(", ".join(portfolio.get("strategies", [])) or "(none)"),
        benchmarks=escape(", ".join(portfolio.get("benchmarks", [])) or "(none)"),
        best_run_name=escape(str(best_run.get("name", "(none)"))),
        best_run_score=escape(str(best_run.get("best_score", ""))),
        total_certainty_conclusions=escape(str(portfolio.get("total_certainty_conclusions", 0))),
        certainty_counts=escape(json.dumps(portfolio.get("certainty_counts", {}), sort_keys=True)),
        best_certainty_run_name=escape(str(best_certainty_run.get("name", "(none)"))),
        best_certainty_run_high=escape(str(best_certainty_run.get("high_certainty_conclusions", ""))),
        total_retries=escape(str(portfolio.get("total_retries", 0))),
        total_tool_calls=escape(str(portfolio.get("total_tool_calls", 0))),
        total_tool_failures=escape(str(portfolio.get("total_tool_failures", 0))),
        unstable_run_name=escape(str(most_unstable_run.get("name", "(none)"))),
        unstable_run_retries=escape(str(most_unstable_run.get("total_retries", ""))),
        runs_table_html=runs_html,
    )
