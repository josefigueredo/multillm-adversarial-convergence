"""Centralized run artifact path construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """All filesystem paths associated with one research run."""

    output_dir: Path
    iterations_dir: Path
    results: Path
    knowledge_base: Path
    synthesis: Path
    methods: Path
    manifest: Path
    metrics: Path
    claims: Path
    citations: Path
    evidence_links: Path
    evidence_quality: Path
    rubric: Path
    contradictions: Path
    certainty_tables: Path
    search_log: Path
    screening_log: Path
    baseline: Path
    evaluation: Path
    comparison: Path
    strategy_summary: Path
    dashboard: Path
    semantic_calibration: Path
    semantic_review: Path
    tool_trace: Path
    prompt_snapshot: Path
    rerun_script: Path
    report_html: Path
    report_pdf: Path
    portfolio: Path
    portfolio_html: Path

    @classmethod
    def for_output_dir(cls, output_dir: Path) -> "RunPaths":
        """Construct all standard artifact paths for *output_dir*."""
        return cls(
            output_dir=output_dir,
            iterations_dir=output_dir / "iterations",
            results=output_dir / "results.tsv",
            knowledge_base=output_dir / "knowledge_base.md",
            synthesis=output_dir / "synthesis.md",
            methods=output_dir / "methods.md",
            manifest=output_dir / "run_manifest.json",
            metrics=output_dir / "metrics.json",
            claims=output_dir / "claims.json",
            citations=output_dir / "citations.json",
            evidence_links=output_dir / "evidence_links.json",
            evidence_quality=output_dir / "evidence_quality.json",
            rubric=output_dir / "rubric.json",
            contradictions=output_dir / "contradictions.json",
            certainty_tables=output_dir / "certainty_tables.json",
            search_log=output_dir / "search_log.json",
            screening_log=output_dir / "screening_log.json",
            baseline=output_dir / "baseline.md",
            evaluation=output_dir / "evaluation.json",
            comparison=output_dir / "comparison.json",
            strategy_summary=output_dir / "strategy_summary.json",
            dashboard=output_dir / "dashboard.json",
            semantic_calibration=output_dir / "semantic_calibration.json",
            semantic_review=output_dir / "semantic_review.json",
            tool_trace=output_dir / "tool_trace.json",
            prompt_snapshot=output_dir / "prompt_snapshot.json",
            rerun_script=output_dir / "rerun.sh",
            report_html=output_dir / "report.html",
            report_pdf=output_dir / "report.pdf",
            portfolio=output_dir.parent / "portfolio.json",
            portfolio_html=output_dir.parent / "portfolio.html",
        )
