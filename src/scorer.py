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

# Point allocation for heuristic scoring components.
#
# The original split (40/35/15/10) was ``dimension`` / ``evidence`` /
# ``new_questions`` / ``length``.  Empirical calibration against the
# localstack_alternatives_copilot_gemini run revealed three weaknesses:
#
# 1. ``dimension`` saturated at full credit on every iteration with the
#    default ``min_dimensions_per_iteration: 1`` — no signal.
# 2. ``evidence`` was driven by per-config regex matches that were
#    misfit for some dimensions (Community activity, Terraform/CDK)
#    yielding 0/35 on legitimate findings.
# 3. ``new_questions`` looked for a ``## New Questions`` section that
#    no shipped research prompt actually asks the model to produce —
#    permanently 0/15.
#
# The redesign replaces those with universal, dimension-agnostic
# signals that correlate with finding quality regardless of topic.
_TARGET_FOCUS_POINTS = 25.0
_CITATIONS_POINTS = 25.0
_CONCRETE_DATA_POINTS = 25.0
_STRUCTURE_POINTS = 15.0
_LENGTH_POINTS = 10.0

_TARGET_WORD_COUNT = 500.0
_TARGET_CITATIONS = 6.0      # findings with 6+ source/url markers max out
_TARGET_CONCRETE_DATA = 12.0 # 12+ specific data points max out
_TARGET_STRUCTURE = 8.0      # 8+ structural elements max out
_MAX_FINDINGS_CHARS = 8000

# Legacy constants retained for backward-compat with any external
# importer; new code should use the universal-signal constants above.
_DIMENSION_POINTS = _TARGET_FOCUS_POINTS
_EVIDENCE_POINTS = _CONCRETE_DATA_POINTS
_NEW_QUESTIONS_POINTS = _STRUCTURE_POINTS
_TARGET_NEW_QUESTIONS = 3.0

# Discovery plan Proposal #1: structured gap shape.
#
# Each gap is now an object with:
#   topic           — the gap itself, 20-200 chars
#   why_it_matters  — one-sentence justification
#   kind            — research_target | refinement | critique
#   investigatable  — true if someone could go research it
#   confidence      — 1 (speculative) to 10 (certain)
#
# The schema also accepts the legacy bare-string shape for transition
# compatibility — `parse_gaps_identified()` normalises either form
# into the structured representation. Once all judges reliably emit
# the new shape we can drop the bare-string branch.
GAP_KINDS = ("research_target", "refinement", "critique")

_STRUCTURED_GAP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "minLength": 20, "maxLength": 200},
        "why_it_matters": {"type": "string", "minLength": 30, "maxLength": 500},
        "kind": {"type": "string", "enum": list(GAP_KINDS)},
        "investigatable": {"type": "boolean"},
        "confidence": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["topic", "why_it_matters", "kind", "investigatable", "confidence"],
}

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
            "items": {
                "oneOf": [
                    _STRUCTURED_GAP_SCHEMA,
                    {"type": "string"},
                ],
            },
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


def parse_gaps_identified(raw_gaps: list[Any]) -> list[dict[str, Any]]:
    """Normalise judge-emitted gaps to the structured shape.

    Accepts either the new structured object form or the legacy bare-
    string form. Bare strings are wrapped with conservative defaults:
    ``kind=research_target``, ``investigatable=true``, ``confidence=5``,
    ``why_it_matters=""``. Items that aren't strings or objects are
    skipped silently.

    Returns a list of dicts with the structured fields plus a
    synthetic ``_source_shape`` field set to "structured" or
    "bare_string" so downstream auditing can tell which judges have
    upgraded.
    """
    normalised: list[dict[str, Any]] = []
    for item in raw_gaps or []:
        if isinstance(item, str):
            topic = item.strip()
            if not topic:
                continue
            normalised.append({
                "topic": topic,
                "why_it_matters": "",
                "kind": "research_target",
                "investigatable": True,
                "confidence": 5,
                "_source_shape": "bare_string",
            })
        elif isinstance(item, dict):
            topic = str(item.get("topic", "")).strip()
            if not topic:
                continue
            kind = item.get("kind", "research_target")
            if kind not in GAP_KINDS:
                kind = "research_target"
            try:
                confidence = int(item.get("confidence", 5))
            except (TypeError, ValueError):
                confidence = 5
            confidence = max(1, min(10, confidence))
            normalised.append({
                "topic": topic,
                "why_it_matters": str(item.get("why_it_matters", "")).strip(),
                "kind": kind,
                "investigatable": bool(item.get("investigatable", True)),
                "confidence": confidence,
                "_source_shape": "structured",
            })
        # Anything else: skip silently
    return normalised


@dataclass
class HeuristicBreakdown:
    """Per-component breakdown of the deterministic heuristic score.

    All values are absolute points awarded for each component (not
    normalised to 0-100).  ``total`` is the normalised 0-100 score
    derived from these components — exactly what ``heuristic_score()``
    returns.

    The five components are dimension-agnostic universal signals:

    Attributes:
        target_focus_points: Points awarded for keyword density of the
            target dimension within the findings, plus a penalty for
            excessive mentions of other configured dimensions
            ("off-topic drift").  Falls back to legacy all-dimensions
            scoring when ``target_dimension`` is None.
        citations_points: Points awarded for citation density —
            URLs, ``[source: ..]`` markers, ``[Issue #..]`` / ``[PR #..]``
            references, and markdown link tokens.  Saturates at
            ``_TARGET_CITATIONS`` matches.
        concrete_data_points: Points awarded for verifiable concrete
            facts — prices, percentages, sizes, durations, version tags,
            ISO dates, full-month dates.  Saturates at
            ``_TARGET_CONCRETE_DATA`` matches.
        structure_points: Points awarded for structural quality —
            markdown tables, code blocks, nested headings, bullet lists.
            Saturates at ``_TARGET_STRUCTURE`` total elements.
        length_points: Points awarded for substantive word count, on a
            logarithmic curve that saturates near ``_TARGET_WORD_COUNT``
            and gives no extra credit for verbose padding.
        total: Normalised 0-100 score combining all components.
        target_dimension: When set, indicates the breakdown was computed
            in target-dimension mode for this dimension.  ``None`` means
            legacy all-dimensions mode.

    Backward-compatibility properties: ``dimension_points``,
    ``evidence_points``, ``new_questions_points`` are aliased to
    ``target_focus_points``, ``concrete_data_points``,
    ``structure_points`` respectively so existing readers (tests,
    log-line, results.tsv writers, dashboard JSON) keep working.
    """

    target_focus_points: float = 0.0
    citations_points: float = 0.0
    concrete_data_points: float = 0.0
    structure_points: float = 0.0
    length_points: float = 0.0
    total: float = 0.0
    target_dimension: str | None = None

    # Aliases for backward-compatible field access. The old four-
    # component model (dimension/evidence/new_questions/length) is
    # mapped onto the new five-component universal-signal model.
    @property
    def dimension_points(self) -> float:
        return self.target_focus_points

    @property
    def evidence_points(self) -> float:
        return self.concrete_data_points

    @property
    def new_questions_points(self) -> float:
        return self.structure_points


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
    # Structured gap records that survived intake filtering. Each item
    # has the shape produced by parse_gaps_identified() plus a
    # canonical_topic field added by process_discovered_gaps(). The
    # bare-string ``gaps`` list above is derived from these records'
    # ``topic`` fields and kept for backward compat. Phase 2 of the
    # discovery plan persists these records via the
    # discovered_gaps.json sidecar; Phase 3 will use them for
    # cross-iteration clustering.
    gap_records: list[dict[str, Any]] = field(default_factory=list)
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

# Universal-signal patterns. These are dimension-agnostic and reward
# concreteness over topic-specific evidence shape.
#
# CITATIONS: bare URLs, [source:..] markers, [Issue #..] / [PR #..]
# refs, and any markdown link `[text](url)` form. Each match counts
# once toward the citation density score.
_CITATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"https?://\S+"),
    re.compile(r"\[source:\s*[^\]]+\]", re.IGNORECASE),
    re.compile(r"\[(?:Issue|PR|RFC)\s*#\d+\]", re.IGNORECASE),
    re.compile(r"\[[^\]]+\]\([^)]+\)"),
]

# CONCRETE DATA: numbers with units. Each match is a verifiable fact
# (a price, a percentage, a release date, a version, a size, a latency,
# a throughput). Tuned to count co-occurring facts only once per
# variant — e.g., a price like "$3.50" matches the price pattern but
# the bare digits inside it don't double-count via the percent pattern.
_CONCRETE_DATA_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\d[\d,]*(?:\.\d+)?\b"),                    # prices
    re.compile(r"\b\d+(?:\.\d+)?\s*%"),                       # percentages
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:GB|MB|KB|TB|kB|gB)\b"), # sizes
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|sec|min|hr|s|h)\b"), # durations
    re.compile(r"\bv\d+\.\d+(?:\.\d+)?\b", re.IGNORECASE),    # version tags
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                     # ISO dates
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
]

# STRUCTURE: presence of formatting elements that distinguish well-
# organised findings from unstructured prose dumps.
_STRUCTURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*\|.*\|.*\|", re.MULTILINE),    # markdown tables
    re.compile(r"```"),                              # code/config blocks
    re.compile(r"^#{2,4}\s+\S", re.MULTILINE),      # nested headings
    re.compile(r"^[\s]*[-*+]\s+\S", re.MULTILINE), # bullet list items
]


def heuristic_breakdown(
    findings: str,
    config: ResearchConfig,
    explored_dimensions: list[str] | None = None,
    *,
    target_dimension: str | None = None,
) -> HeuristicBreakdown:
    """Score research findings using deterministic heuristics, returning
    the per-component breakdown.

    Five universal, dimension-agnostic components:

    - **target_focus** (``_TARGET_FOCUS_POINTS``): keyword density of
      the assigned dimension when ``target_dimension`` is set; legacy
      "any configured dimension mentioned" credit otherwise.  In
      target mode the score splits 70% on-target / 30% no-drift.
    - **citations** (``_CITATIONS_POINTS``): count of URLs, source
      markers, issue refs, markdown links — saturated via log curve.
    - **concrete_data** (``_CONCRETE_DATA_POINTS``): count of verifiable
      facts (prices, percentages, sizes, durations, versions, dates) —
      saturated via log curve.
    - **structure** (``_STRUCTURE_POINTS``): tables + code blocks +
      nested headings + bullet density — saturated via log curve.
    - **length** (``_LENGTH_POINTS``): word count on a log curve.

    Args:
        findings: Raw markdown findings text.
        config: Research config; used for dimension list when scoring
            target focus.
        explored_dimensions: Accepted for backward compatibility;
            currently unused.
        target_dimension: When set, score target_focus against this
            specific dimension; otherwise legacy any-dimension credit.

    Returns:
        A ``HeuristicBreakdown`` with per-component points and the
        normalised 0-100 ``total``.
    """
    breakdown = HeuristicBreakdown(target_dimension=target_dimension)

    if not findings:
        return breakdown

    max_points = (
        _TARGET_FOCUS_POINTS
        + _CITATIONS_POINTS
        + _CONCRETE_DATA_POINTS
        + _STRUCTURE_POINTS
        + _LENGTH_POINTS
    )
    all_dims = list(config.dimensions)

    # --- Target focus (dimension relevance) ---
    if not all_dims:
        max_points -= _TARGET_FOCUS_POINTS
    elif target_dimension is not None:
        on_target_weight = _TARGET_FOCUS_POINTS * 0.7
        drift_weight = _TARGET_FOCUS_POINTS * 0.3

        if _fuzzy_match(target_dimension, findings):
            breakdown.target_focus_points += on_target_weight

        other_dims = [d for d in all_dims if d != target_dimension]
        if other_dims:
            mentions = sum(1 for d in other_dims if _fuzzy_match(d, findings))
            drift_ratio = mentions / len(other_dims)
            breakdown.target_focus_points += drift_weight * (1.0 - drift_ratio)
        else:
            breakdown.target_focus_points += drift_weight
    else:
        mentioned = sum(1 for d in all_dims if _fuzzy_match(d, findings))
        breakdown.target_focus_points = _TARGET_FOCUS_POINTS * min(
            mentioned / max(config.scoring.min_dimensions_per_iteration, 1), 1.0
        )

    # --- Citations (universal — works for any dimension) ---
    citation_count = sum(
        len(pattern.findall(findings)) for pattern in _CITATION_PATTERNS
    )
    if citation_count > 0:
        breakdown.citations_points = min(
            _CITATIONS_POINTS,
            _CITATIONS_POINTS * math.log(citation_count + 1) / math.log(_TARGET_CITATIONS + 1),
        )

    # --- Concrete data (verifiable facts; universal) ---
    concrete_count = sum(
        len(pattern.findall(findings)) for pattern in _CONCRETE_DATA_PATTERNS
    )
    if concrete_count > 0:
        breakdown.concrete_data_points = min(
            _CONCRETE_DATA_POINTS,
            _CONCRETE_DATA_POINTS * math.log(concrete_count + 1) / math.log(_TARGET_CONCRETE_DATA + 1),
        )

    # --- Structure (formatting elements; universal) ---
    structure_count = sum(
        len(pattern.findall(findings)) for pattern in _STRUCTURE_PATTERNS
    )
    if structure_count > 0:
        breakdown.structure_points = min(
            _STRUCTURE_POINTS,
            _STRUCTURE_POINTS * math.log(structure_count + 1) / math.log(_TARGET_STRUCTURE + 1),
        )

    # --- Substantive length (logarithmic curve, no padding bonus) ---
    word_count = len(findings.split())
    if word_count > 0:
        # log(501) * 1.61 ~= 10.0; calibrated so 500 words lands at cap.
        breakdown.length_points = min(_LENGTH_POINTS, math.log(word_count + 1) * 1.61)

    points = (
        breakdown.target_focus_points
        + breakdown.citations_points
        + breakdown.concrete_data_points
        + breakdown.structure_points
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
