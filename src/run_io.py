"""Filesystem persistence helpers for run artifacts and iteration logs."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scorer import IterationScore


RESULTS_FIELDS = [
    "iteration",
    "timestamp",
    "dimension",
    "coverage_score",
    "quality_score",
    "total_score",
    "status",
    "hypothesis",
    "discovered_gaps",
    "cumulative_cost_usd",
    "cumulative_input_tokens",
    "cumulative_output_tokens",
    # --- Score component breakdown (additive; new columns at end so
    # existing tsv readers continue to work without changes) ---
    "dimension_points",
    "evidence_points",
    "new_questions_points",
    "length_points",
    "judge_depth",
    "judge_accuracy",
    "judge_novelty",
    "judge_actionability",
]


def setup_output_dir(output_dir: Path, iterations_dir: Path) -> None:
    """Ensure the output directory layout exists."""
    output_dir.mkdir(parents=True, exist_ok=True)
    iterations_dir.mkdir(exist_ok=True)


def write_results_header(results_path: Path) -> None:
    """Write the header row to a new results.tsv file."""
    with open(results_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()


def build_result_row(
    *,
    iteration: int,
    dimension: str,
    score: IterationScore,
    hypothesis: str,
    status: str,
    total_cost_usd: float,
    total_input_tokens: int,
    total_output_tokens: int,
) -> dict[str, str]:
    """Build a results.tsv row."""
    breakdown = score.heuristic_breakdown
    return {
        "iteration": f"{iteration:03d}",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "dimension": dimension,
        "coverage_score": f"{score.coverage:.1f}",
        "quality_score": f"{score.quality:.1f}",
        "total_score": f"{score.total:.1f}",
        "status": status,
        "hypothesis": hypothesis[:120],
        "discovered_gaps": json.dumps(score.gaps),
        "cumulative_cost_usd": f"{total_cost_usd:.3f}",
        "cumulative_input_tokens": str(total_input_tokens),
        "cumulative_output_tokens": str(total_output_tokens),
        "dimension_points": f"{breakdown.dimension_points:.1f}",
        "evidence_points": f"{breakdown.evidence_points:.1f}",
        "new_questions_points": f"{breakdown.new_questions_points:.1f}",
        "length_points": f"{breakdown.length_points:.1f}",
        "judge_depth": str(score.judge_depth),
        "judge_accuracy": str(score.judge_accuracy),
        "judge_novelty": str(score.judge_novelty),
        "judge_actionability": str(score.judge_actionability),
    }


def append_result_row(results_path: Path, row: dict[str, str]) -> None:
    """Append a row to results.tsv."""
    with open(results_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()), delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(row)


def write_iteration_markdown(
    *,
    iterations_dir: Path,
    iteration: int,
    dimension: str,
    findings: str,
    score: IterationScore,
    kept: bool,
) -> Path:
    """Write a numbered iteration markdown file with a per-component
    score breakdown so operators can read why a score landed where it
    did without having to crack open dashboard.json or results.tsv.
    """
    path = iterations_dir / f"iter_{iteration:03d}.md"
    breakdown = score.heuristic_breakdown
    content = (
        f"# Iteration {iteration:03d} — {dimension}\n\n"
        f"**Status:** {'keep' if kept else 'discard'}  \n"
        f"**Scores:** coverage={score.coverage}, quality={score.quality}, "
        f"total={score.total}  \n"
        f"**Heuristic breakdown:** "
        f"target/dimension={breakdown.dimension_points:.1f}/40, "
        f"evidence={breakdown.evidence_points:.1f}/35, "
        f"new_questions={breakdown.new_questions_points:.1f}/15, "
        f"length={breakdown.length_points:.1f}/10  \n"
        f"**Judge axes (1-10):** depth={score.judge_depth}, "
        f"accuracy={score.judge_accuracy}, novelty={score.judge_novelty}, "
        f"actionability={score.judge_actionability}  \n"
        f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}  \n\n"
        f"---\n\n{findings}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path
