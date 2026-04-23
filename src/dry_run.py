"""Dry-run planning helpers for research runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .run_paths import RunPaths


def build_dry_run_summary(
    *,
    config: Any,
    config_path: Path,
    output_dir: Path,
    backends: dict[str, Any],
) -> dict[str, Any]:
    """Build a dry-run validation summary without executing the research loop."""
    paths = RunPaths.for_output_dir(output_dir)
    provider_entries = {
        name: {
            "adapter": provider.adapter,
            "model": provider.model,
        }
        for name, provider in config.providers.items()
    }
    return {
        "mode": "run",
        "config_path": str(config_path.resolve()),
        "topic": config.topic,
        "goal": config.goal,
        "strategy": config.execution.strategy,
        "primary_backend": config.execution.backends.primary,
        "backend_roles": {
            "primary": config.execution.backends.primary,
            "research": list(config.execution.backends.research),
            "judge": config.execution.backends.judge_or_primary,
            "utility": config.execution.backends.utility_or_primary,
        },
        "resolved_backends": sorted(backends.keys()),
        "providers_count": len(config.providers),
        "providers": provider_entries,
        "output_dir": str(output_dir.resolve()),
        "flags": {
            "stream": config.execution.stream,
            "retry_api_errors": config.execution.retry_api_errors,
            "system_prompt": bool(config.execution.system_prompt.strip()),
            "allowed_tools": bool(config.execution.allowed_tools.strip()),
        },
        "artifacts": {
            "manifest": str(paths.manifest.resolve()),
            "metrics": str(paths.metrics.resolve()),
            "prompt_snapshot": str(paths.prompt_snapshot.resolve()),
            "dashboard": str(paths.dashboard.resolve()),
            "report_html": str(paths.report_html.resolve()),
        },
    }


def render_dry_run_summary(summary: dict[str, Any]) -> str:
    """Render a human-readable dry-run summary."""
    lines = [
        "DRY RUN OK",
        f"mode: {summary['mode']}",
        f"config: {summary['config_path']}",
        f"topic: {summary['topic']}",
        f"strategy: {summary['strategy']}",
        f"primary backend: {summary['primary_backend']}",
        f"research backends: {', '.join(summary['backend_roles']['research'])}",
        f"resolved backends: {', '.join(summary['resolved_backends'])}",
        f"output_dir: {summary['output_dir']}",
        f"providers: {summary['providers_count']}",
        f"stream: {'enabled' if summary['flags']['stream'] else 'disabled'}",
        f"retry_api_errors: {summary['flags']['retry_api_errors']}",
        f"system_prompt: {'configured' if summary['flags']['system_prompt'] else 'absent'}",
        f"allowed_tools: {'configured' if summary['flags']['allowed_tools'] else 'absent'}",
        "planned artifacts:",
    ]
    if "primary_artifact" in summary:
        lines.insert(7, f"primary artifact: {summary['primary_artifact']}")
    for name, path in summary["artifacts"].items():
        lines.append(f"  - {name}: {path}")
    return "\n".join(lines)


def build_convergence_dry_run_summary(
    *,
    mode: str,
    config: Any,
    config_path: Path,
    output_dir: Path,
    backends: dict[str, Any],
) -> dict[str, Any]:
    """Build a dry-run summary for refine/plan convergence modes."""
    return {
        "mode": mode,
        "config_path": str(config_path.resolve()),
        "topic": config.topic,
        "goal": config.goal,
        "strategy": getattr(config, "execution", None).strategy if getattr(config, "execution", None) else "single",
        "primary_backend": config.backends.primary,
        "backend_roles": {
            "primary": config.backends.primary,
            "research": list(config.backends.research),
            "judge": config.backends.judge_or_primary,
            "utility": config.backends.utility_or_primary,
        },
        "resolved_backends": sorted(backends.keys()),
        "providers_count": len(config.providers),
        "providers": {
            name: {"adapter": provider.adapter, "model": provider.model}
            for name, provider in config.providers.items()
        },
        "output_dir": str(output_dir.resolve()),
        "flags": {
            "stream": False,
            "retry_api_errors": 0,
            "system_prompt": False,
            "allowed_tools": False,
        },
        "primary_artifact": config.primary_artifact,
        "artifacts": {
            "primary_artifact": str((output_dir / config.primary_artifact).resolve()),
            "dashboard": str((output_dir / "dashboard.json").resolve()),
            "report_html": str((output_dir / "report.html").resolve()),
        },
    }
