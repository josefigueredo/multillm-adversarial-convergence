"""Hybrid scoring: heuristic analysis + LLM-as-judge.

The heuristic scorer counts evidence types, dimension mentions, and
structural markers in research findings.  The LLM judge provides a
qualitative assessment via a separate Claude call.  Both scores are
combined with configurable weights.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .config import ResearchConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEURISTIC_WEIGHT = 0.4
JUDGE_WEIGHT = 0.6

# Point allocation for heuristic scoring components
_DIMENSION_POINTS = 40.0
_EVIDENCE_POINTS = 35.0
_NEW_QUESTIONS_POINTS = 15.0
_LENGTH_POINTS = 10.0
_TARGET_WORD_COUNT = 500.0
_TARGET_NEW_QUESTIONS = 3.0
_MAX_FINDINGS_CHARS = 8000

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "depth": {"type": "integer", "minimum": 1, "maximum": 10},
        "accuracy": {"type": "integer", "minimum": 1, "maximum": 10},
        "novelty": {"type": "integer", "minimum": 1, "maximum": 10},
        "actionability": {"type": "integer", "minimum": 1, "maximum": 10},
        "dimensions_covered": {
            "type": "array",
            "items": {"type": "string"},
        },
        "gaps_identified": {
            "type": "array",
            "items": {"type": "string"},
        },
        "reasoning": {"type": "string"},
    },
    "required": [
        "depth",
        "accuracy",
        "novelty",
        "actionability",
        "dimensions_covered",
        "gaps_identified",
        "reasoning",
    ],
    "additionalProperties": False,
}


@dataclass
class HeuristicBreakdown:
    """Per-component breakdown of the deterministic heuristic score.

    All values are absolute points awarded for each component (not
    normalised to 0-100).  ``total`` is the normalised 0-100 score
    derived from these components — exactly what ``heuristic_score()``
    returns.

    Attributes:
        dimension_points: Points awarded for dimension-relevance (out of
            ``_DIMENSION_POINTS``).  In target-dimension mode this rewards
            depth on the assigned dimension and penalises off-topic drift;
            in legacy "all-dimensions" mode it rewards mentioning many of
            the configured dimensions.
        evidence_points: Points awarded for finding configured evidence
            types in the findings (out of ``_EVIDENCE_POINTS``).
        new_questions_points: Points awarded for the count of new
            questions in the ``## New Questions`` section (out of
            ``_NEW_QUESTIONS_POINTS``).
        length_points: Points awarded for substantive word count, on a
            logarithmic curve that saturates near ``_TARGET_WORD_COUNT``
            and gives no extra credit for verbose padding (out of
            ``_LENGTH_POINTS``).
        total: Normalised 0-100 score combining all components.
        target_dimension: When set, indicates the breakdown was computed
            in target-dimension mode for this dimension.  ``None`` means
            legacy all-dimensions mode.
    """

    dimension_points: float = 0.0
    evidence_points: float = 0.0
    new_questions_points: float = 0.0
    length_points: float = 0.0
    total: float = 0.0
    target_dimension: str | None = None


@dataclass
class IterationScore:
    """Scores for a single research iteration.

    Attributes:
        coverage: Heuristic coverage score (0-100).
        quality: LLM judge quality score (0-100).
        total: Weighted combination of coverage and quality (0-100).
        dimensions_covered: Dimensions the judge identified as covered.
        gaps: Knowledge gaps the judge identified.
        judge_raw: Raw JSON response from the LLM judge.
        heuristic_breakdown: Per-component decomposition of ``coverage``.
        judge_depth: Judge's depth axis score (1-10) extracted from
            ``judge_raw``; 0 when missing.
        judge_accuracy: Judge's accuracy axis score (1-10).
        judge_novelty: Judge's novelty axis score (1-10).  Surfaced
            independently so downstream consumers (and Phase 2 of the
            scoring plan) can use novelty as a signal without re-rolling
            the judge call.
        judge_actionability: Judge's actionability axis score (1-10).
    """

    coverage: float = 0.0
    quality: float = 0.0
    total: float = 0.0
    dimensions_covered: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    judge_raw: dict[str, Any] = field(default_factory=dict)
    heuristic_breakdown: HeuristicBreakdown = field(default_factory=HeuristicBreakdown)
    judge_depth: int = 0
    judge_accuracy: int = 0
    judge_novelty: int = 0
    judge_actionability: int = 0


# ---------------------------------------------------------------------------
# Heuristic scoring (deterministic, fast)
# ---------------------------------------------------------------------------

_EVIDENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "comparison_table": re.compile(r"\|.*\|.*\|", re.MULTILINE),
    "pricing_data": re.compile(r"\$[\d,.]+|USD|per.?million|free.?tier", re.IGNORECASE),
    "code_example": re.compile(r"```"),
    "architecture_diagram_description": re.compile(
        r"architecture|diagram|flow|topology", re.IGNORECASE
    ),
    "trade_off_analysis": re.compile(
        r"trade.?off|downside|caveat|however|on the other hand", re.IGNORECASE
    ),
}


def heuristic_breakdown(
    findings: str,
    config: ResearchConfig,
    explored_dimensions: list[str] | None = None,
    *,
    target_dimension: str | None = None,
) -> HeuristicBreakdown:
    """Score research findings using deterministic heuristics, returning
    the per-component breakdown.

    Evaluates four components:
    - Dimension relevance (``_DIMENSION_POINTS`` pts).  When
      ``target_dimension`` is provided, 70% of the weight goes to depth
      on the target dimension and 30% goes to "no off-topic drift" — a
      penalty for excessive mentions of other configured dimensions.
      When ``target_dimension`` is None, falls back to legacy behavior:
      one point per configured dimension that appears in the findings.
    - Evidence types found (``_EVIDENCE_POINTS`` pts).
    - New questions discovered (``_NEW_QUESTIONS_POINTS`` pts).
    - Substantive word count (``_LENGTH_POINTS`` pts).  Logarithmic curve
      that saturates near ``_TARGET_WORD_COUNT`` and gives no padding
      bonus for verbose findings beyond the target.

    Args:
        findings: Raw markdown findings text.
        config: Research config with dimensions and scoring settings.
        explored_dimensions: Previously explored dimensions.  Currently
            unused (reserved for future weighting); accepted for
            backward compatibility.
        target_dimension: When set, score dimension-relevance against
            this specific dimension instead of the full configured list.
            Required for focused-iteration scoring; ``None`` recovers
            the legacy all-dimensions behavior.

    Returns:
        A ``HeuristicBreakdown`` with per-component points and the
        normalised 0-100 ``total``.
    """
    breakdown = HeuristicBreakdown(target_dimension=target_dimension)

    if not findings:
        return breakdown

    max_points = _DIMENSION_POINTS + _EVIDENCE_POINTS + _NEW_QUESTIONS_POINTS + _LENGTH_POINTS
    all_dims = list(config.dimensions)

    # --- Dimension relevance ---
    if not all_dims:
        # No dimensions configured — don't penalise, redistribute weight.
        max_points -= _DIMENSION_POINTS
    elif target_dimension is not None:
        # Target-dimension mode: reward depth on the assigned dimension,
        # penalise off-topic drift.  Splits _DIMENSION_POINTS 70/30.
        on_target_weight = _DIMENSION_POINTS * 0.7
        drift_weight = _DIMENSION_POINTS * 0.3

        if _fuzzy_match(target_dimension, findings):
            breakdown.dimension_points += on_target_weight

        # Drift score: full credit when no other dimensions are
        # mentioned; linear penalty up to the full drift_weight as the
        # number of off-target dimensions present grows.
        other_dims = [d for d in all_dims if d != target_dimension]
        if other_dims:
            mentions = sum(1 for d in other_dims if _fuzzy_match(d, findings))
            drift_ratio = mentions / len(other_dims)
            breakdown.dimension_points += drift_weight * (1.0 - drift_ratio)
        else:
            breakdown.dimension_points += drift_weight
    else:
        # Legacy mode: one point per configured dimension mentioned,
        # normalised to ``min_dimensions_per_iteration``.
        mentioned = sum(1 for d in all_dims if _fuzzy_match(d, findings))
        breakdown.dimension_points = _DIMENSION_POINTS * min(
            mentioned / max(config.scoring.min_dimensions_per_iteration, 1), 1.0
        )

    # --- Evidence types ---
    types_found = sum(
        1
        for etype, pattern in _EVIDENCE_PATTERNS.items()
        if etype in config.scoring.evidence_types and pattern.search(findings)
    )
    target_evidence = len(config.scoring.evidence_types)
    if target_evidence:
        breakdown.evidence_points = _EVIDENCE_POINTS * min(types_found / target_evidence, 1.0)

    # --- New questions discovered ---
    new_q_section = _extract_section(findings, "New Questions")
    if new_q_section:
        bullet_count = len(re.findall(r"^[\s]*[-*]\s", new_q_section, re.MULTILINE))
        breakdown.new_questions_points = _NEW_QUESTIONS_POINTS * min(
            bullet_count / _TARGET_NEW_QUESTIONS, 1.0
        )

    # --- Substantive length (logarithmic curve, no padding bonus) ---
    word_count = len(findings.split())
    if word_count > 0:
        # Calibrated so words ~= _TARGET_WORD_COUNT (500) lands near the
        # cap.  log(501) * 1.61 ~= 10.0.  Capped so verbose findings
        # don't beat focused ones on this axis.
        breakdown.length_points = min(_LENGTH_POINTS, math.log(word_count + 1) * 1.61)

    points = (
        breakdown.dimension_points
        + breakdown.evidence_points
        + breakdown.new_questions_points
        + breakdown.length_points
    )
    breakdown.total = round(100.0 * points / max_points, 1) if max_points > 0 else 0.0
    return breakdown


def heuristic_score(
    findings: str,
    config: ResearchConfig,
    explored_dimensions: list[str] | None = None,
    *,
    target_dimension: str | None = None,
) -> float:
    """Thin wrapper over :func:`heuristic_breakdown` returning only the
    normalised 0-100 total.  Preserved for backward-compatible call
    sites that don't need the component breakdown.
    """
    return heuristic_breakdown(
        findings,
        config,
        explored_dimensions,
        target_dimension=target_dimension,
    ).total


# ---------------------------------------------------------------------------
# LLM judge scoring
# ---------------------------------------------------------------------------

def parse_judge_response(raw_text: str) -> dict[str, Any]:
    """Extract a JSON object from the LLM judge's response.

    Tolerates markdown fences and surrounding prose.

    Args:
        raw_text: Raw text output from the judge Claude call.

    Returns:
        Parsed JSON as a dict.

    Raises:
        json.JSONDecodeError: If no valid JSON object can be extracted.
    """
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    elif text.startswith("{"):
        pass
    else:
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            text = text[brace_start : brace_end + 1]

    return json.loads(text)


def quality_score_from_judge(judge: dict[str, Any]) -> float:
    """Convert LLM judge axes (1-10 each) into a 0-100 quality score.

    Missing axes default to 5 (neutral).

    Args:
        judge: Parsed judge response with ``depth``, ``accuracy``,
            ``novelty``, and ``actionability`` keys.

    Returns:
        Quality score from 0.0 to 100.0.
    """
    axes = ["depth", "accuracy", "novelty", "actionability"]
    raw = sum(judge.get(a, 5) for a in axes)
    return round(raw / (len(axes) * 10) * 100.0, 1)


def combine_scores(coverage: float, quality: float) -> float:
    """Weighted combination of heuristic and judge scores.

    Uses ``HEURISTIC_WEIGHT`` (40%) and ``JUDGE_WEIGHT`` (60%).

    Args:
        coverage: Heuristic coverage score (0-100).
        quality: LLM judge quality score (0-100).

    Returns:
        Combined score from 0.0 to 100.0.
    """
    return round(HEURISTIC_WEIGHT * coverage + JUDGE_WEIGHT * quality, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KEEP_THRESHOLD = 30.0


def compute_inter_rater_agreement(
    assessments: list[Any],
    *,
    keep_threshold: float = _KEEP_THRESHOLD,
) -> dict[str, Any]:
    """Compute inter-rater agreement from multi-candidate assessments.

    Groups assessments by dimension.  For each dimension with 2+ candidates,
    records the per-backend scores and whether both backends agreed on the
    keep/discard decision (score >= *keep_threshold*).

    When 2+ dimensions have multi-candidate data, computes Cohen's kappa
    on the binary keep/discard decisions.

    Args:
        assessments: List of ``CandidateAssessment`` objects (from
            ``LoopState.candidate_assessments``).
        keep_threshold: Score at or above which findings are considered
            "keep".  Matches the threshold in ``run_iteration``.

    Returns:
        Agreement summary dict.  Empty ``per_dimension`` list when no
        multi-candidate data exists.
    """
    from collections import defaultdict

    by_dim: dict[str, list[Any]] = defaultdict(list)
    for a in assessments:
        by_dim[a.dimension].append(a)

    per_dimension: list[dict[str, Any]] = []
    for dim, items in by_dim.items():
        if len(items) < 2:
            continue
        entries = [
            {"backend": a.backend_name, "coverage": a.coverage, "quality": a.quality, "total": a.total}
            for a in items
        ]
        decisions = [a.total >= keep_threshold for a in items]
        per_dimension.append({
            "dimension": dim,
            "assessments": entries,
            "decision_agreed": len(set(decisions)) == 1,
        })

    n_dims = len(per_dimension)
    if n_dims == 0:
        return {
            "dimensions_with_multiple_candidates": 0,
            "decision_agreement_rate": None,
            "cohens_kappa": None,
            "mean_score_delta": None,
            "per_dimension": [],
        }

    agreed = sum(1 for d in per_dimension if d["decision_agreed"])
    agreement_rate = round(agreed / n_dims, 2)

    deltas = []
    for d in per_dimension:
        scores = [a["total"] for a in d["assessments"]]
        deltas.append(max(scores) - min(scores))
    mean_delta = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

    kappa = _cohens_kappa(per_dimension, keep_threshold) if n_dims >= 2 else None

    return {
        "dimensions_with_multiple_candidates": n_dims,
        "decision_agreement_rate": agreement_rate,
        "cohens_kappa": kappa,
        "mean_score_delta": mean_delta,
        "per_dimension": per_dimension,
    }


def _cohens_kappa(
    per_dimension: list[dict[str, Any]],
    keep_threshold: float,
) -> float | None:
    """Compute Cohen's kappa on binary keep/discard decisions.

    Uses the first two assessments per dimension as rater A and rater B.
    Returns None if there are fewer than 2 dimensions or if the expected
    agreement is 1.0 (all same category → kappa undefined).
    """
    if len(per_dimension) < 2:
        return None

    # Build 2x2 contingency: (raterA_keep, raterB_keep)
    a_b = {"kk": 0, "kd": 0, "dk": 0, "dd": 0}
    for d in per_dimension:
        items = d["assessments"]
        a_keep = items[0]["total"] >= keep_threshold
        b_keep = items[1]["total"] >= keep_threshold
        if a_keep and b_keep:
            a_b["kk"] += 1
        elif a_keep and not b_keep:
            a_b["kd"] += 1
        elif not a_keep and b_keep:
            a_b["dk"] += 1
        else:
            a_b["dd"] += 1

    n = sum(a_b.values())
    if n == 0:
        return None
    p_o = (a_b["kk"] + a_b["dd"]) / n  # observed agreement
    p_a_keep = (a_b["kk"] + a_b["kd"]) / n
    p_b_keep = (a_b["kk"] + a_b["dk"]) / n
    p_e = p_a_keep * p_b_keep + (1 - p_a_keep) * (1 - p_b_keep)  # expected by chance

    if p_e >= 1.0:
        return None  # degenerate: all same category
    return round((p_o - p_e) / (1.0 - p_e), 2)


def _fuzzy_match(dimension: str, text: str) -> bool:
    """Check if key terms from a dimension label appear in the text.

    Words with 3 or fewer characters are ignored.  A match requires at
    least half of the remaining keywords to be present (case-insensitive).
    """
    keywords = [w.lower() for w in dimension.split() if len(w) > 3]
    if not keywords:
        return False
    matches = sum(1 for kw in keywords if kw in text.lower())
    return matches >= max(len(keywords) // 2, 1)


def _extract_section(text: str, heading: str) -> str:
    """Extract the content under a markdown heading.

    Returns the text between the matched heading and the next heading of
    equal or higher level, or end of string.
    """
    pattern = rf"^#+\s*{re.escape(heading)}.*?\n(.*?)(?=^#+\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""
