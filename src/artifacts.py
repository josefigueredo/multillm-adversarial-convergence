"""Artifact payload builders, filesystem loading, and environment helpers."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import shlex
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .output_style import build_output_style_presentation, summarize_output_style_overrides


def derive_report_title(*, report_title: str, topic: str, synthesis_text: str) -> str:
    """Derive a concise report title from explicit config, synthesis heading, or topic."""
    if report_title.strip():
        return report_title.strip()

    synthesis_heading = _extract_markdown_heading(synthesis_text)
    if synthesis_heading:
        return synthesis_heading

    return _shorten_topic_title(topic)


def _extract_markdown_heading(text: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text or "")
    return match.group(1).strip() if match else ""


def _shorten_topic_title(topic: str) -> str:
    cleaned = " ".join((topic or "").split()).strip()
    if not cleaned:
        return "Autoresearch Report"
    for phrase in (", given that", ", focusing on", ", evaluate", ", assess", ", compare"):
        idx = cleaned.lower().find(phrase)
        if idx > 0:
            candidate = cleaned[:idx].strip(" ,")
            if candidate:
                return candidate
    for delimiter in (". ", "; ", ": ", " — ", " - "):
        if delimiter in cleaned:
            candidate = cleaned.split(delimiter, 1)[0].strip()
            if candidate:
                return candidate
    if "," in cleaned:
        candidate = cleaned.split(",", 1)[0].strip()
        if candidate:
            return candidate
    if len(cleaned) <= 80:
        return cleaned
    words = cleaned.split()
    out: list[str] = []
    total = 0
    for word in words:
        extra = len(word) + (1 if out else 0)
        if total + extra > 80:
            break
        out.append(word)
        total += extra
    return " ".join(out) if out else cleaned[:80].rstrip()


def load_json_if_exists(path: Path, default: Any) -> Any:
    """Return parsed JSON from *path* when it exists, else *default*."""
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def run_manifest_payload(
    *,
    config: Any,
    strategy_description: str,
    backends: dict[str, Any],
    output_dir: Path,
    resume: bool,
    config_path: Path | None,
    run_status: str,
    run_started_at: str | None,
    run_completed_at: str | None,
    package_version: str | None,
    git_commit: str | None,
    cli_version_resolver: Any,
) -> dict[str, Any]:
    """Build the machine-readable manifest payload for a run."""
    return {
        "project": {
            "name": "autoresearch",
            "version": package_version,
        },
        "run": {
            "status": run_status,
            "started_at": run_started_at,
            "completed_at": run_completed_at,
            "resume_requested": resume,
            "output_dir": str(output_dir.resolve()),
        },
        "config": {
            "path": str(config_path.resolve()) if config_path else None,
            "snapshot": asdict(config),
        },
        "strategy": {
            "name": config.execution.strategy,
            "description": strategy_description,
        },
        "evaluation": {
            "benchmark_id": config.evaluation.benchmark_id,
            "run_baselines": config.evaluation.run_baselines,
            "semantic_review": config.evaluation.semantic_review,
        },
        "reporting": {
            "export_html": config.reporting.export_html,
            "export_pdf": config.reporting.export_pdf,
            "report_title": config.reporting.report_title,
            "output_style": config.reporting.output_style,
            "output_style_label": build_output_style_presentation(config.reporting.output_style)["style_label"],
            "style_overrides": asdict(config.reporting.style_overrides),
            "active_style_overrides": summarize_output_style_overrides(config.reporting.style_overrides),
        },
        "environment": {
            "python_version": __import__("platform").python_version(),
            "platform": __import__("platform").platform(),
            "git_commit": git_commit,
        },
        "reproducibility": {
            "prompt_snapshot_path": str((output_dir / "prompt_snapshot.json").resolve()),
            "rerun_script_path": str((output_dir / "rerun.sh").resolve()),
        },
        "backends": {
            name: {
                "cli": backend.cli_executable(),
                "version": cli_version_resolver(backend.cli_executable()),
            }
            for name, backend in backends.items()
        },
    }


def prompt_snapshot_payload(
    *,
    prompts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a prompt-snapshot artifact payload."""
    entries: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        text = str(prompt.get("prompt", ""))
        entry = dict(prompt)
        entry.setdefault("index", index)
        entry["prompt_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entries.append(entry)
    return {
        "entries_count": len(entries),
        "entries": entries,
    }


def rerun_script_text(
    *,
    config_path: Path | None,
    output_dir: Path,
) -> str:
    """Build a shell script that replays the run with the same config."""
    config_arg = shlex.quote(str(config_path.resolve() if config_path else output_dir / "config.yaml"))
    output_arg = shlex.quote(str(output_dir.resolve()))
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n\n"
        "# Re-run this research job with the same config and output directory.\n"
        "# Tip: override the output directory by editing the command below or copying it elsewhere.\n"
        f"autoresearch run --config {config_arg} --output {output_arg} \"$@\"\n"
    )


def metrics_payload(
    *,
    benchmark_id: str,
    run_status: str,
    iteration: int,
    best_score: float,
    explored_dimensions: list[str],
    discovered_dimensions: list[str],
    total_cost: float,
    total_input_tokens: int,
    total_output_tokens: int,
    per_backend_costs: dict[str, float],
    per_backend_tokens: dict[str, dict[str, int]],
    results: list[dict[str, str]],
    retry_summary: dict[str, Any] | None = None,
    tool_loop_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable metrics payload."""
    return {
        "run_status": run_status,
        "benchmark_id": benchmark_id,
        "iterations": iteration,
        "best_score": best_score,
        "explored_dimensions_count": len(explored_dimensions),
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
        "total_cost_usd": total_cost,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "per_backend_costs": per_backend_costs,
        "per_backend_tokens": per_backend_tokens,
        "results": results,
        "retry_summary": retry_summary or {
            "total_retries": 0,
            "per_backend": {},
            "per_category": {},
            "per_backend_category": {},
        },
        "tool_loop_summary": tool_loop_summary or {
            "runs": 0,
            "tool_calls": 0,
            "tool_failures": 0,
            "per_backend": {},
            "per_tool": {},
        },
    }


def should_write_evaluation(config: Any) -> bool:
    """Return True when any evaluation artifact should be emitted."""
    return bool(
        config.evaluation.run_baselines
        or config.evaluation.benchmark_id
        or config.evaluation.reference_runs
        or config.evaluation.semantic_review
    )


def evaluation_payload(
    *,
    benchmark_id: str,
    baseline_exists: bool,
    claims: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    evidence_quality: dict[str, Any],
    rubric: dict[str, Any],
    benchmark_summary: dict[str, Any],
    reference_comparison: dict[str, Any],
    semantic_review: dict[str, Any],
    semantic_calibration: dict[str, Any],
) -> dict[str, Any]:
    """Build the aggregated evaluation artifact payload."""
    baseline_claims = [claim for claim in claims if claim.get("scope") == "baseline"]
    synthesis_claims = [claim for claim in claims if claim.get("scope") == "synthesis"]
    baseline_citations = [citation for citation in citations if citation.get("scope") == "baseline"]
    synthesis_citations = [citation for citation in citations if citation.get("scope") == "synthesis"]
    return {
        "benchmark_id": benchmark_id,
        "baseline_generated": baseline_exists,
        "iterative_synthesis": {
            "claims_count": len(synthesis_claims),
            "citations_count": len(synthesis_citations),
        },
        "baseline": {
            "claims_count": len(baseline_claims),
            "citations_count": len(baseline_citations),
        },
        "evidence_quality": evidence_quality,
        "rubric": rubric,
        "benchmark": benchmark_summary,
        "reference_comparison": reference_comparison,
        "semantic_review": semantic_review,
        "semantic_calibration": semantic_calibration,
        "summary": {
            "iterative_has_more_claims_than_baseline": len(synthesis_claims) > len(baseline_claims),
            "iterative_has_more_citations_than_baseline": len(synthesis_citations) > len(baseline_citations),
            "benchmark_expectations_satisfied": benchmark_summary.get("all_expectations_satisfied", True),
            "reference_runs_compared": reference_comparison.get("compared_runs_count", 0),
            "rubric_grade": rubric.get("grade", "insufficient"),
            "semantic_review_grade": semantic_review.get("grade", "disabled"),
            "semantic_calibration_grade": semantic_calibration.get("grade", "disabled"),
        },
    }


def dashboard_payload(
    *,
    topic: str,
    goal: str,
    benchmark_id: str,
    current_strategy: str,
    output_style: str,
    output_style_label: str,
    active_style_overrides: list[str] | None,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
    comparison: dict[str, Any],
    evaluation: dict[str, Any],
    strategy_summary: dict[str, Any],
    semantic_calibration: dict[str, Any],
    semantic_review: dict[str, Any],
    certainty_summary: dict[str, Any] | None = None,
    search_log_summary: dict[str, Any] | None = None,
    screening_log_summary: dict[str, Any] | None = None,
    retry_summary: dict[str, Any] | None = None,
    tool_loop_summary: dict[str, Any] | None = None,
    tool_trace_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stakeholder-facing dashboard artifact payload."""
    tool_usage_summary = _tool_usage_summary(tool_loop_summary or {})
    retry_insights = _retry_insights(retry_summary or {})
    return {
        "topic": topic,
        "goal": goal,
        "benchmark_id": benchmark_id,
        "current_strategy": current_strategy,
        "output_style": output_style,
        "output_style_label": output_style_label,
        "active_style_overrides": active_style_overrides or [],
        "best_score": best_score,
        "rubric_grade": rubric.get("grade", "insufficient"),
        "rubric_overall_score": rubric.get("overall_score", 0.0),
        "evidence_quality_score": evidence_quality.get("average_evidence_quality_score", 0.0),
        "iterations": iteration,
        "explored_dimensions_count": len(explored_dimensions),
        "explored_dimensions": explored_dimensions,
        "strategy_summary": strategy_summary,
        "consistency_level": comparison.get("summary", {}).get("consistency_level", "not_available"),
        "reference_runs_compared": comparison.get("compared_runs_count", 0),
        "benchmark_expectations_satisfied": evaluation.get("summary", {}).get(
            "benchmark_expectations_satisfied", True
        ),
        "semantic_calibration": semantic_calibration,
        "semantic_review": semantic_review,
        "certainty_summary": certainty_summary or {
            "conclusions_count": 0,
            "certainty_counts": {},
            "high_certainty_factual_count": 0,
            "high_certainty_recommendation_count": 0,
        },
        "search_log_summary": search_log_summary or {
            "queries_count": 0,
            "sources_considered": 0,
        },
        "screening_log_summary": screening_log_summary or {
            "sources_screened": 0,
            "included_count": 0,
            "excluded_count": 0,
        },
        "retry_summary": retry_summary or {
            "total_retries": 0,
            "per_backend": {},
            "per_category": {},
            "per_backend_category": {},
        },
        "retry_insights": retry_insights,
        "tool_loop_summary": tool_loop_summary or {
            "runs": 0,
            "tool_calls": 0,
            "tool_failures": 0,
            "per_backend": {},
            "per_tool": {},
        },
        "tool_usage_summary": tool_usage_summary,
        "tool_trace_summary": tool_trace_summary or {
            "entries_count": 0,
            "status_counts": {},
            "top_failure_codes": [],
        },
    }


def tool_trace_payload(*, tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a machine-readable tool trace artifact payload."""
    return {
        "entries_count": len(tool_trace),
        "summary": _tool_trace_summary(tool_trace),
        "redaction_policy": {
            "sensitive_values": "redacted",
            "argument_string_preview_chars": 120,
            "output_preview_chars": 240,
            "sequence_preview_items": 5,
        },
        "entries": tool_trace,
    }


def _tool_trace_summary(tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Build compact report-friendly tool trace highlights."""
    status_counts: dict[str, int] = {}
    failure_codes: dict[str, int] = {}
    for entry in tool_trace:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status", "") or "")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
        if status == "error":
            provider_code = str(entry.get("provider_code", "") or "unknown")
            failure_codes[provider_code] = failure_codes.get(provider_code, 0) + 1

    top_failure_codes = [
        {"provider_code": code, "count": count}
        for code, count in failure_codes.items()
    ]
    top_failure_codes.sort(key=lambda item: (-item["count"], item["provider_code"]))
    return {
        "entries_count": len(tool_trace),
        "status_counts": status_counts,
        "top_failure_codes": top_failure_codes[:5],
    }


def _tool_usage_summary(tool_loop_summary: dict[str, Any]) -> dict[str, Any]:
    """Build compact report-friendly tool usage highlights."""
    per_tool = tool_loop_summary.get("per_tool", {})
    per_backend = tool_loop_summary.get("per_backend", {})
    top_tools = [
        {
            "name": name,
            "calls": int(stats.get("calls", 0) or 0),
            "failures": int(stats.get("failures", 0) or 0),
        }
        for name, stats in per_tool.items()
        if isinstance(stats, dict)
    ]
    top_tools.sort(key=lambda item: (-item["calls"], item["name"]))

    failure_hotspots: list[dict[str, Any]] = []
    for backend_name, backend_stats in per_backend.items():
        if not isinstance(backend_stats, dict):
            continue
        for tool_name, tool_stats in (backend_stats.get("tools", {}) or {}).items():
            if not isinstance(tool_stats, dict):
                continue
            failures = int(tool_stats.get("failures", 0) or 0)
            if failures <= 0:
                continue
            failure_hotspots.append(
                {
                    "backend": backend_name,
                    "tool_name": tool_name,
                    "failures": failures,
                }
            )
    failure_hotspots.sort(key=lambda item: (-item["failures"], item["backend"], item["tool_name"]))

    return {
        "top_tools": top_tools[:5],
        "failure_hotspots": failure_hotspots[:5],
    }


def _retry_insights(retry_summary: dict[str, Any]) -> dict[str, Any]:
    """Build compact report-friendly retry highlights."""
    per_backend = retry_summary.get("per_backend", {})
    per_category = retry_summary.get("per_category", {})

    unstable = [
        {"backend": backend, "retries": int(count or 0)}
        for backend, count in per_backend.items()
    ]
    unstable.sort(key=lambda item: (-item["retries"], item["backend"]))

    categories = [
        {"category": category, "count": int(count or 0)}
        for category, count in per_category.items()
    ]
    categories.sort(key=lambda item: (-item["count"], item["category"]))

    return {
        "most_unstable_backend": unstable[0] if unstable else {},
        "top_retry_categories": categories[:5],
    }


def pdf_run_summary_text(
    *,
    topic: str,
    goal: str,
    strategy: str,
    output_style: str,
    output_style_label: str,
    active_style_overrides: list[str] | None,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    metrics: dict[str, Any],
    rubric: dict[str, Any],
    evidence_quality: dict[str, Any],
) -> str:
    """Format core run summary text for PDF export."""
    certainty_summary = metrics.get("certainty_summary", {}) if isinstance(metrics, dict) else {}
    tool_loop = metrics.get("tool_loop_summary", {}) if isinstance(metrics, dict) else {}
    retry_summary = metrics.get("retry_summary", {}) if isinstance(metrics, dict) else {}
    certainty_line = ""
    if isinstance(certainty_summary, dict) and int(certainty_summary.get("conclusions_count", 0) or 0) > 0:
        counts = certainty_summary.get("certainty_counts", {})
        top_band = ""
        if isinstance(counts, dict) and counts:
            top_band = max(counts.items(), key=lambda item: int(item[1] or 0))[0]
        certainty_line = (
            f"Certainty: {int(certainty_summary.get('conclusions_count', 0) or 0)} "
            f"conclusions / top band {top_band} / high-certainty recommendations "
            f"{int(certainty_summary.get('high_certainty_recommendation_count', 0) or 0)}\n"
        )
    tool_line = ""
    if isinstance(tool_loop, dict) and int(tool_loop.get("runs", 0) or 0) > 0:
        tool_line = (
            f"Tool loops: {int(tool_loop.get('runs', 0) or 0)} runs / "
            f"{int(tool_loop.get('tool_calls', 0) or 0)} calls / "
            f"{int(tool_loop.get('tool_failures', 0) or 0)} failures\n"
        )
    retry_line = ""
    if isinstance(retry_summary, dict) and int(retry_summary.get("total_retries", 0) or 0) > 0:
        retry_line = f"API retries: {int(retry_summary.get('total_retries', 0) or 0)}\n"
    return (
        f"Topic: {topic}\n"
        f"Goal: {goal}\n"
        f"Strategy: {strategy}\n"
        f"Output style: {output_style} ({output_style_label})\n"
        f"Style overrides: {', '.join(active_style_overrides or []) or 'none'}\n"
        f"Best score: {metrics.get('best_score', best_score)}\n"
        f"Iterations: {metrics.get('iterations', iteration)}\n"
        f"Rubric grade: {rubric.get('grade', 'insufficient')}\n"
        f"Evidence quality: {evidence_quality.get('average_evidence_quality_score', 0.0)}\n"
        f"Explored dimensions: {', '.join(metrics.get('explored_dimensions', explored_dimensions)) or '(none)'}\n"
        f"{certainty_line}"
        f"{tool_line}"
        f"{retry_line}"
    )


def certainty_pdf_text(certainty_tables: dict[str, Any]) -> str:
    """Format certainty-table details for PDF export."""
    if not isinstance(certainty_tables, dict):
        return ""
    summary = certainty_tables.get("summary", {})
    conclusions = certainty_tables.get("conclusions", [])
    if not isinstance(summary, dict) or not isinstance(conclusions, list):
        return ""
    count = int(summary.get("conclusions_count", 0) or 0)
    if count <= 0:
        return ""
    lines = [
        f"Conclusions: {count}",
        f"High-certainty recommendations: {int(summary.get('high_certainty_recommendation_count', 0) or 0)}",
    ]
    for conclusion in conclusions[:5]:
        if not isinstance(conclusion, dict):
            continue
        lines.append(
            f"- {conclusion.get('dimension', 'overall')}: {conclusion.get('certainty', 'unknown')}"
        )
        factors = conclusion.get("factors", {})
        if isinstance(factors, dict):
            for factor_name, factor in factors.items():
                if not isinstance(factor, dict):
                    continue
                lines.append(
                    f"  - {factor_name}: {factor.get('level', 'unknown')} — {factor.get('reason', '')}"
                )
    return "\n".join(lines)


def git_commit() -> str | None:
    """Return the current git commit SHA if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def cli_version(executable: str) -> str | None:
    """Return a CLI version string when available."""
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def package_version() -> str | None:
    """Return the installed autoresearch package version if available."""
    try:
        return importlib.metadata.version("autoresearch")
    except importlib.metadata.PackageNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Artifact writers — standalone functions that load from disk and write output
# ---------------------------------------------------------------------------


def write_html_report(
    output_dir: Path,
    *,
    config: Any,
    render_fn: Any,
) -> None:
    """Render a standalone HTML report when enabled in config.

    Args:
        output_dir: Run output directory containing artifact JSON files.
        config: The ``ResearchConfig`` for this run.
        render_fn: The ``render_html_report`` function from ``reporting.py``.
    """
    if not config.reporting.export_html:
        return

    manifest = load_json_if_exists(output_dir / "run_manifest.json", {})
    metrics = load_json_if_exists(output_dir / "metrics.json", {})
    evidence_quality = load_json_if_exists(output_dir / "evidence_quality.json", {})
    rubric = load_json_if_exists(output_dir / "rubric.json", {})
    evaluation = load_json_if_exists(output_dir / "evaluation.json", None)
    comparison = load_json_if_exists(output_dir / "comparison.json", None)
    semantic_calibration = load_json_if_exists(output_dir / "semantic_calibration.json", None)
    semantic_review = load_json_if_exists(output_dir / "semantic_review.json", None)
    certainty_tables = load_json_if_exists(output_dir / "certainty_tables.json", None)
    dashboard = load_json_if_exists(output_dir / "dashboard.json", None)
    methods_path = output_dir / "methods.md"
    synthesis_path = output_dir / "synthesis.md"
    methods_text = methods_path.read_text(encoding="utf-8") if methods_path.exists() else ""
    synthesis_text = synthesis_path.read_text(encoding="utf-8") if synthesis_path.exists() else ""
    title = derive_report_title(
        report_title=config.reporting.report_title,
        topic=config.topic,
        synthesis_text=synthesis_text,
    )
    html = render_fn(
        title=title,
        output_style=config.reporting.output_style,
        topic=config.topic,
        goal=config.goal,
        manifest=manifest,
        metrics=metrics,
        evidence_quality=evidence_quality,
        rubric=rubric,
        evaluation=evaluation,
        comparison=comparison,
        semantic_calibration=semantic_calibration,
        semantic_review=semantic_review,
        certainty_tables=certainty_tables,
        dashboard=dashboard,
        methods_text=methods_text,
        synthesis_text=synthesis_text,
    )
    (output_dir / "report.html").write_text(html, encoding="utf-8")


def write_pdf_report(
    output_dir: Path,
    *,
    config: Any,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    render_pdf_fn: Any,
) -> None:
    """Render a simple PDF report when enabled in config."""
    if not config.reporting.export_pdf:
        return

    presentation = build_output_style_presentation(config.reporting.output_style)
    metrics = load_json_if_exists(output_dir / "metrics.json", {})
    rubric = load_json_if_exists(output_dir / "rubric.json", {})
    evidence_quality = load_json_if_exists(output_dir / "evidence_quality.json", {})
    evaluation = load_json_if_exists(output_dir / "evaluation.json", {})
    dashboard = load_json_if_exists(output_dir / "dashboard.json", {})
    certainty_tables = load_json_if_exists(output_dir / "certainty_tables.json", {})
    methods_path = output_dir / "methods.md"
    synthesis_path = output_dir / "synthesis.md"
    methods_text = methods_path.read_text(encoding="utf-8") if methods_path.exists() else ""
    synthesis_text = synthesis_path.read_text(encoding="utf-8") if synthesis_path.exists() else ""
    title = derive_report_title(
        report_title=config.reporting.report_title,
        topic=config.topic,
        synthesis_text=synthesis_text,
    ) + presentation["pdf_title_suffix"]
    sections = [
        (
            "Run Summary",
            pdf_run_summary_text(
                topic=config.topic,
                goal=config.goal,
                strategy=config.execution.strategy,
                output_style=config.reporting.output_style,
                output_style_label=presentation["style_label"],
                active_style_overrides=summarize_output_style_overrides(config.reporting.style_overrides),
                best_score=best_score,
                iteration=iteration,
                explored_dimensions=explored_dimensions,
                metrics=metrics,
                rubric=rubric,
                evidence_quality=evidence_quality,
            ),
        ),
        ("Certainty", certainty_pdf_text(certainty_tables)),
        (presentation["methods_heading"], methods_text),
        (presentation["synthesis_heading"], synthesis_text),
        ("Dashboard", json.dumps(dashboard, indent=2)),
        ("Evaluation", json.dumps(evaluation, indent=2)),
    ]
    (output_dir / "report.pdf").write_bytes(render_pdf_fn(title, sections))


def write_dashboard(
    output_dir: Path,
    *,
    config: Any,
    best_score: float,
    iteration: int,
    explored_dimensions: list[str],
    retry_summary: dict[str, Any] | None = None,
    tool_loop_summary: dict[str, Any] | None = None,
) -> None:
    """Write a stakeholder-friendly summary dashboard artifact."""
    rubric = load_json_if_exists(output_dir / "rubric.json", {})
    evidence_quality = load_json_if_exists(output_dir / "evidence_quality.json", {})
    comparison = load_json_if_exists(output_dir / "comparison.json", {})
    evaluation = load_json_if_exists(output_dir / "evaluation.json", {})
    strategy_summary = load_json_if_exists(output_dir / "strategy_summary.json", {})
    semantic_calibration = load_json_if_exists(output_dir / "semantic_calibration.json", {})
    semantic_review = load_json_if_exists(output_dir / "semantic_review.json", {})
    certainty_tables = load_json_if_exists(output_dir / "certainty_tables.json", {})
    search_log = load_json_if_exists(output_dir / "search_log.json", {})
    screening_log = load_json_if_exists(output_dir / "screening_log.json", {})
    tool_trace = load_json_if_exists(output_dir / "tool_trace.json", {})

    payload = dashboard_payload(
        topic=config.topic,
        goal=config.goal,
        benchmark_id=config.evaluation.benchmark_id,
        current_strategy=config.execution.strategy,
        output_style=config.reporting.output_style,
        output_style_label=build_output_style_presentation(config.reporting.output_style)["style_label"],
        active_style_overrides=summarize_output_style_overrides(config.reporting.style_overrides),
        best_score=best_score,
        iteration=iteration,
        explored_dimensions=explored_dimensions,
        rubric=rubric,
        evidence_quality=evidence_quality,
        comparison=comparison,
        evaluation=evaluation,
        strategy_summary=strategy_summary,
        semantic_calibration=semantic_calibration,
        semantic_review=semantic_review,
        certainty_summary=certainty_tables.get("summary", {}) if isinstance(certainty_tables, dict) else {},
        search_log_summary=search_log.get("summary", {}) if isinstance(search_log, dict) else {},
        screening_log_summary=screening_log.get("summary", {}) if isinstance(screening_log, dict) else {},
        retry_summary=retry_summary,
        tool_loop_summary=tool_loop_summary,
        tool_trace_summary=tool_trace.get("summary", {}) if isinstance(tool_trace, dict) else {},
    )
    (output_dir / "dashboard.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_portfolio(output_dir: Path, portfolio_fn: Any, portfolio_html_fn: Any) -> None:
    """Aggregate sibling run dashboards into a portfolio summary."""
    output_root = output_dir.parent
    if not output_root.exists():
        return
    portfolio = portfolio_fn(output_root)
    (output_dir.parent / "portfolio.json").write_text(json.dumps(portfolio, indent=2), encoding="utf-8")
    (output_dir.parent / "portfolio.html").write_text(
        portfolio_html_fn("Autoresearch Portfolio", portfolio),
        encoding="utf-8",
    )
