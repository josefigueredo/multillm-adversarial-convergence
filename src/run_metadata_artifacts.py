"""Helpers for run-manifest and metrics artifact persistence."""

from __future__ import annotations

import json
from typing import Any

from .artifacts import cli_version, git_commit, metrics_payload, package_version, run_manifest_payload


def write_run_metadata_artifacts(researcher: Any) -> None:
    """Write machine-readable manifest and metrics artifacts for a run."""
    manifest = run_manifest_payload(
        config=researcher.config,
        strategy_description=researcher.strategy.describe(),
        backends=researcher.backends,
        output_dir=researcher.output_dir,
        resume=researcher.resume,
        config_path=researcher.config_path,
        run_status=researcher._run_status,
        run_started_at=researcher._run_started_at,
        run_completed_at=researcher._run_completed_at,
        package_version=package_version(),
        git_commit=git_commit(),
        cli_version_resolver=cli_version,
    )
    researcher.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    metrics = metrics_payload(
        benchmark_id=researcher.config.evaluation.benchmark_id,
        run_status=researcher._run_status,
        iteration=researcher.iteration,
        best_score=researcher.best_score,
        explored_dimensions=researcher.explored_dimensions,
        discovered_dimensions=researcher.discovered_dimensions,
        total_cost=researcher.total_cost,
        total_input_tokens=researcher.total_input_tokens,
        total_output_tokens=researcher.total_output_tokens,
        per_backend_costs=researcher.per_backend_costs,
        per_backend_tokens=researcher.per_backend_tokens,
        results=researcher.results,
        retry_summary=researcher._retry_summary,
        tool_loop_summary=researcher._tool_loop_summary,
    )
    researcher.metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
