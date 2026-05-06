#!/usr/bin/env python3
"""Replay heuristic scoring against an existing run's iteration findings.

For each ``iter_NNN.md`` in a run output directory, compute the
heuristic breakdown in BOTH legacy mode (no ``target_dimension``) and
target-dimension mode (the new Phase 1 behavior).  Print a comparison
table per iteration and aggregate deltas so the operator can see —
empirically and in milliseconds, with zero LLM calls — whether the
breadth-bias fix actually changes scores in the predicted direction.

Predicted direction (from docs/plans/scoring-enhancements.md, Phase 1):

- Iter 1 (broad first pass): coverage drops slightly because it no
  longer earns credit for touching dimensions other than its target.
- Iter 2-6 (focused): coverage RISES because the new mode rewards
  depth on the assigned dimension instead of penalising the focus.

Usage:
    uv run python scripts/calibrate_scoring.py \
        --run output/localstack_alternatives_copilot_gemini \
        --config configs/research/localstack_alternatives_copilot_gemini.yaml
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import ResearchConfig
from src.scorer import HeuristicBreakdown, heuristic_breakdown


@dataclass
class IterRecord:
    num: int
    dimension: str
    findings: str
    original_coverage: float
    original_quality: float
    original_total: float


_HEADER_DIMENSION = re.compile(r"^# Iteration \d+ — (.+)$", re.MULTILINE)
_HEADER_SCORES = re.compile(
    r"\*\*Scores:\*\*\s+coverage=([\d.]+),\s+quality=([\d.]+),\s+total=([\d.]+)"
)


def parse_iter_file(path: Path) -> IterRecord:
    text = path.read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n\n")
    dim_match = _HEADER_DIMENSION.search(head)
    score_match = _HEADER_SCORES.search(head)
    if not dim_match or not score_match:
        raise ValueError(f"Could not parse iter header in {path}")
    num = int(re.search(r"iter_(\d+)", path.name).group(1))
    return IterRecord(
        num=num,
        dimension=dim_match.group(1).strip(),
        findings=body,
        original_coverage=float(score_match.group(1)),
        original_quality=float(score_match.group(2)),
        original_total=float(score_match.group(3)),
    )


def fmt(bd: HeuristicBreakdown) -> str:
    return (
        f"target_focus={bd.target_focus_points:>5.1f}/25  "
        f"citations={bd.citations_points:>5.1f}/25  "
        f"data={bd.concrete_data_points:>5.1f}/25  "
        f"structure={bd.structure_points:>5.1f}/15  "
        f"length={bd.length_points:>5.1f}/10"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()

    cfg = ResearchConfig.from_yaml(args.config)
    iters_dir = args.run / "iterations"
    iter_files = sorted(iters_dir.glob("iter_*.md"))

    print(f"\nReplaying heuristic scoring against {iters_dir}")
    print(f"Config: {args.config}")
    print(f"Configured dimensions: {len(cfg.dimensions)}")
    print()

    legacy_totals = []
    target_totals = []

    print("=" * 100)
    print(f"{'iter':>4}  {'mode':<8}  {'coverage':>8}  components")
    print("-" * 100)

    for f in iter_files:
        rec = parse_iter_file(f)
        legacy = heuristic_breakdown(rec.findings, cfg, [])
        target = heuristic_breakdown(
            rec.findings, cfg, [], target_dimension=rec.dimension
        )
        legacy_totals.append(legacy.total)
        target_totals.append(target.total)
        delta = target.total - legacy.total

        print(f"\nDimension: {rec.dimension}")
        print(
            f"  Original (committed)  cov={rec.original_coverage:>5.1f}  qual={rec.original_quality:>5.1f}  "
            f"total={rec.original_total:>5.1f}"
        )
        print(f"  {rec.num:>4}  legacy    {legacy.total:>8.1f}  {fmt(legacy)}")
        print(f"  {rec.num:>4}  target    {target.total:>8.1f}  {fmt(target)}")
        sign = "+" if delta >= 0 else ""
        print(f"  {rec.num:>4}  Δ                                                 {sign}{delta:.1f}")

    print()
    print("=" * 100)
    print("Aggregate")
    print("-" * 100)
    print(f"  Mean coverage (legacy mode):    {sum(legacy_totals) / len(legacy_totals):>5.1f}")
    print(f"  Mean coverage (target-dim mode): {sum(target_totals) / len(target_totals):>5.1f}")
    print(f"  Stdev legacy:  {_stdev(legacy_totals):>5.1f}")
    print(f"  Stdev target:  {_stdev(target_totals):>5.1f}")
    print()


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return var ** 0.5


if __name__ == "__main__":
    main()
