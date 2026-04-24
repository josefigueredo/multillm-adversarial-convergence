"""Human-readable config and run-state explainers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .output_style import build_output_style_presentation, summarize_output_style_overrides
from .run_paths import RunPaths


def explain_config_text(config: Any, *, config_path: Path | None = None) -> str:
    """Render a human-readable explanation of the effective research config.

    Does NOT create output directories, run backends, or instantiate any
    execution machinery.  Pure inspection of the resolved config object.
    """
    lines: list[str] = []

    if config_path is not None:
        lines.append(f"config: {config_path.resolve()}")

    # --- Research topic / goal -------------------------------------------------
    lines += [
        "",
        "RESEARCH",
        f"  topic:    {config.topic}",
        f"  goal:     {config.goal}",
    ]
    if config.dimensions:
        lines.append(f"  dimensions ({len(config.dimensions)}):")
        for dim in config.dimensions:
            lines.append(f"    - {dim}")
    else:
        lines.append("  dimensions: none configured")

    # --- Strategy / execution --------------------------------------------------
    lines += [
        "",
        "STRATEGY",
        f"  strategy:       {config.execution.strategy}",
        f"  max_iterations: {config.execution.max_iterations or 'unlimited'}",
        f"  stream:         {'enabled' if config.execution.stream else 'disabled'}",
    ]

    # --- Backend role mapping --------------------------------------------------
    backends = config.execution.backends
    lines += [
        "",
        "BACKEND ROLES",
        f"  primary:  {backends.primary}",
        f"  research: {', '.join(backends.research) if backends.research else '—'}",
        f"  judge:    {backends.judge_or_primary}",
        f"  utility:  {backends.utility_or_primary}",
    ]

    # --- Provider instances ----------------------------------------------------
    if config.providers:
        lines.append("")
        lines.append(f"PROVIDERS ({len(config.providers)})")
        for name, provider in config.providers.items():
            model_part = f" ({provider.model})" if getattr(provider, "model", None) else ""
            lines.append(f"  {name}: {provider.adapter}{model_part}")

    # --- Output style ----------------------------------------------------------
    style_label = build_output_style_presentation(config.reporting.output_style).get(
        "style_label", config.reporting.output_style
    )
    active_overrides = summarize_output_style_overrides(config.reporting.style_overrides)
    lines += [
        "",
        "OUTPUT STYLE",
        f"  style:     {config.reporting.output_style} ({style_label})",
        f"  overrides: {', '.join(active_overrides) if active_overrides else 'none'}",
    ]

    # --- Reporting outputs ----------------------------------------------------
    lines += [
        "",
        "REPORTING",
        f"  html: {'enabled' if config.reporting.export_html else 'disabled'}",
        f"  pdf:  {'enabled' if config.reporting.export_pdf else 'disabled'}",
    ]
    if config.reporting.report_title:
        lines.append(f"  title: {config.reporting.report_title}")

    # --- Security policy -------------------------------------------------------
    sec = config.security
    sb = sec.sandbox
    lines += [
        "",
        "SECURITY POLICY",
        f"  content_trust:       {sec.content_trust}",
        f"  tool_execution_mode: {sec.tool_execution_mode}",
        f"  allow_host_bash:     {sec.allow_host_bash}",
        f"  filesystem_writes_outside_output: {sec.allow_filesystem_write_outside_output}",
        f"  sandbox.mode:        {sb.mode}",
        f"  sandbox.scope:       {sb.scope}",
        f"  sandbox.filesystem:  {sb.filesystem_access}",
        f"  sandbox.network:     {sb.network_access}",
    ]

    # --- Artifact paths (dry-run preview) --------------------------------------
    stem = config_path.stem if config_path is not None else "run"
    output_dir = Path("output") / stem
    paths = RunPaths.for_output_dir(output_dir)
    lines += [
        "",
        "ARTIFACTS (default output paths)",
        f"  output_dir:       {output_dir}",
        f"  effective_config: {paths.effective_config}",
        f"  manifest:         {paths.manifest}",
        f"  report_html:      {paths.report_html}",
    ]

    return "\n".join(lines)


def explain_resume_text(output_dir: Path) -> str:
    """Inspect an existing output directory and explain its resume state.

    Does NOT create directories, run backends, or instantiate any execution
    machinery.  Pure filesystem inspection of the saved run state.
    """
    if not output_dir.exists():
        return f"output directory not found: {output_dir}"

    paths = RunPaths.for_output_dir(output_dir)

    iter_files = (
        sorted(paths.iterations_dir.glob("iter_*.md"))
        if paths.iterations_dir.exists()
        else []
    )
    iteration_count = len(iter_files)

    artifact_checks = [
        ("iterations", paths.iterations_dir.exists() and iteration_count > 0),
        ("results.tsv", paths.results.exists()),
        ("knowledge_base.md", paths.knowledge_base.exists()),
        ("synthesis.md", paths.synthesis.exists()),
        ("report.html", paths.report_html.exists()),
        ("metrics.json", paths.metrics.exists()),
        ("effective_config.json", paths.effective_config.exists()),
        ("audit_trail.jsonl", paths.audit_trail.exists()),
    ]
    artifact_map = dict(artifact_checks)

    best_score: float | None = None
    run_status: str | None = None
    if paths.metrics.exists():
        try:
            data = json.loads(paths.metrics.read_text(encoding="utf-8"))
            best_score = data.get("best_score")
            run_status = data.get("run_status")
        except (json.JSONDecodeError, OSError):
            pass

    can_resume = iteration_count > 0
    is_complete = artifact_map["synthesis.md"] and artifact_map["report.html"]

    lines: list[str] = [f"output: {output_dir.resolve()}", ""]

    lines += ["RESUME STATUS", f"  resumable:        {'yes' if can_resume else 'no (no iteration files found)'}"]
    lines.append(f"  iterations_found: {iteration_count}")
    if best_score is not None:
        lines.append(f"  best_score:       {best_score}")
    if run_status:
        lines.append(f"  run_status:       {run_status}")
    if is_complete:
        lines.append("  note:             run appears complete (synthesis + report present)")

    lines += ["", "ARTIFACTS"]
    for name, present in artifact_checks:
        mark = "\u2713" if present else "\u2717"
        if name == "iterations":
            label = f"iterations ({iteration_count} files)" if present else "iterations (none found)"
        else:
            label = name
        lines.append(f"  {mark} {label}")

    reused: list[str] = []
    if iteration_count > 0:
        reused.append(f"{iteration_count} iteration file(s) (iter_*.md)")
    if artifact_map["results.tsv"]:
        reused.append("results.tsv (score history)")
    if artifact_map["knowledge_base.md"]:
        reused.append("knowledge_base.md (accumulated findings)")

    lines += ["", "ON RESUME — REUSED"]
    if reused:
        for item in reused:
            lines.append(f"  - {item}")
    else:
        lines.append("  (nothing — no resumable state found)")

    lines += [
        "",
        "ON RESUME — REGENERATED",
        "  - synthesis.md",
        "  - methods.md",
        "  - dashboard.json",
        "  - report.html",
        "  - report.pdf",
    ]

    return "\n".join(lines)
