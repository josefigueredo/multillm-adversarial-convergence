"""Human-readable config and run-state explainers."""

from __future__ import annotations

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
