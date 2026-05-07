"""Core research iteration loop.

Extracted from orchestrator.py to isolate the hypothesis -> research ->
score -> keep/discard cycle.  All backend invocation goes through
callbacks on the LoopContext so this module has no direct backend
dependency.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .backends import AgentResponse
from .config import ResearchConfig
from .prompts import render as _render
from .run_io import append_result_row, build_result_row, write_iteration_markdown
from .run_state import (
    BaseContext,
    GapEntry,
    maybe_exhaust_dimension,
    merge_findings,
    record_gap,
)
from .scorer import (
    IterationScore,
    combine_scores,
    combine_scores_weighted,
    heuristic_breakdown,
    heuristic_score,
    novelty_score,
    parse_gaps_identified,
    parse_judge_response,
    quality_score_from_judge,
)
from .strategy import ResearchCandidate
from .workflows.research_states import ResearchState
from .workflows.decisions import IterationDecision
from .workflows.transitions import WorkflowTransitionEmitter

log = logging.getLogger(__name__)

_MAX_FINDINGS_CHARS = 60_000


@dataclass
class LoopContext(BaseContext):
    """Immutable bundle of callbacks and config for the research loop.

    Extends ``BaseContext`` which provides: ``call_with``,
    ``invoke_for_strategy``, ``track_usage``, ``track_cost``.
    """

    config: ResearchConfig
    strategy: Any
    track_candidate_usage: Callable[[ResearchCandidate], None]
    collect_provenance: Callable[..., None]
    methodology_summary: Callable[[], str]
    kb_summary: Callable[[], str]
    format_dimension_list: Callable[[list[str]], str]
    goal_constraints_summary: Callable[[], str]
    audit_trail: Any
    artifact_root: Path


@dataclass
class CandidateAssessment:
    """Score snapshot for one backend's findings on a dimension.

    Collected during multi-candidate selection so inter-rater agreement
    can be computed after the run.  Without this, per-candidate scores
    are discarded when the winner is selected.
    """

    iteration: int
    dimension: str
    backend_name: str
    coverage: float
    quality: float
    total: float


@dataclass
class LoopState:
    """Mutable state for the research loop, shared with the orchestrator."""

    knowledge_base: str = ""
    kb_path: Path = field(default_factory=lambda: Path("knowledge_base.md"))
    explored_dimensions: list[str] = field(default_factory=list)
    # Legacy bare-string view of discovered gaps.  Kept in lock-step
    # with ``discovered_gaps`` (the structured dict) via the
    # ``record_gap`` helper.  The hypothesis prompt and other
    # downstream consumers continue to use this list directly; the
    # structured dict is the source of truth for sidecar persistence,
    # Phase 3 clustering, and Phase 4 dispatch.
    discovered_dimensions: list[str] = field(default_factory=list)
    discovered_gaps: dict[str, "GapEntry"] = field(default_factory=dict)
    # Discovery plan Phase 4: kind-based dispatch.  Refinement requests
    # target existing explored dimensions for re-investigation;
    # critiques are stored for the synthesis report but never enter
    # the hypothesis pool.  Both are derived views of
    # ``discovered_gaps`` filtered by ``kind`` and ``promoted`` —
    # populated by ``rebuild_kind_views()`` after each iteration.
    refinement_requests: list[str] = field(default_factory=list)
    critiques: list[dict[str, Any]] = field(default_factory=list)
    dimension_attempts: dict[str, int] = field(default_factory=dict)
    best_score: float = 0.0
    best_scores: dict[str, float] = field(default_factory=dict)
    iteration: int = 0
    results: list[dict[str, str]] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    iterations_dir: Path = field(default_factory=lambda: Path("iterations"))
    results_path: Path = field(default_factory=lambda: Path("results.tsv"))
    candidate_assessments: list[CandidateAssessment] = field(default_factory=list)
    current_workflow_state: ResearchState = ResearchState.IDLE
    # Most recent IterationScore produced by ``_score()``.  Surfaced
    # back to the orchestrator via ``_sync_from_loop_state`` so the
    # dashboard's ``latest_score_breakdown`` payload can be populated.
    latest_score: Any = None

    MAX_ATTEMPTS_PER_DIMENSION: int = 3
    KB_MAX_WORDS: int = 8000


def run_iteration(ctx: LoopContext, state: LoopState) -> None:
    """Execute one full research iteration (hypothesis -> execute -> score -> decide)."""
    state.iteration += 1
    log.info("=" * 60)
    log.info("Iteration %03d", state.iteration)
    log.info("=" * 60)
    ctx.audit_trail.emit("iteration_started", iteration=state.iteration)

    emitter = WorkflowTransitionEmitter(ctx.audit_trail, "research", state.current_workflow_state)

    hypothesis = _generate_hypothesis(ctx, state)
    if not hypothesis:
        log.warning("Hypothesis generation failed, retrying next iteration.")
        ctx.audit_trail.emit(
            "iteration_aborted",
            iteration=state.iteration,
            reason="hypothesis_generation_failed",
        )
        # Hypothesis did not succeed — no phase transition emitted; state unchanged.
        return

    # Hypothesis phase completed successfully.
    emitter.transition(ResearchState.HYPOTHESIS, iteration=state.iteration)

    dimension = hypothesis.get("dimension", "unknown")
    questions = hypothesis.get("questions", [])
    approach = hypothesis.get("approach", "")

    state.dimension_attempts[dimension] = state.dimension_attempts.get(dimension, 0) + 1
    attempts = state.dimension_attempts[dimension]
    log.info("Dimension: %s (attempt %d/%d)", dimension, attempts, state.MAX_ATTEMPTS_PER_DIMENSION)

    findings = _execute_research(ctx, state, dimension, questions, approach)
    if not findings:
        log.warning("Research execution returned empty, logging crash.")
        _log_result(ctx, state, dimension, IterationScore(), "", status=IterationDecision.CRASH)
        _maybe_exhaust(state, dimension)
        ctx.audit_trail.emit(
            "iteration_aborted",
            iteration=state.iteration,
            dimension=dimension,
            reason="research_execution_empty",
        )
        # Execute did not succeed — persist HYPOTHESIS as current state (hypothesis was done).
        state.current_workflow_state = emitter.current_state
        return

    # Execute phase completed successfully.
    emitter.transition(ResearchState.EXECUTE, iteration=state.iteration, dimension=dimension)

    score = _score(ctx, state, dimension, findings)
    state.latest_score = score
    prev_best = state.best_scores.get(dimension, 0.0)
    breakdown = score.heuristic_breakdown
    log.info(
        "Scores — coverage: %.1f [target=%.1f/%.0f evidence=%.1f/%.0f questions=%.1f/%.0f length=%.1f/%.0f] "
        "quality: %.1f [d=%d a=%d n=%d act=%d] novelty: %.1f total: %.1f (dim best: %.1f, global best: %.1f)",
        score.coverage,
        breakdown.dimension_points, 40.0,
        breakdown.evidence_points, 35.0,
        breakdown.new_questions_points, 15.0,
        breakdown.length_points, 10.0,
        score.quality,
        score.judge_depth, score.judge_accuracy, score.judge_novelty, score.judge_actionability,
        score.heuristic_novelty,
        score.total,
        prev_best, state.best_score,
    )
    emitter.transition(ResearchState.SCORE, iteration=state.iteration, dimension=dimension)

    # Scoring plan Proposal #8: cross-iteration depth bonus.  When a
    # dimension is re-attempted (attempt N >= 2), the KEEP gate's
    # ``> prev_best`` comparison is multiplied by a depth-multiplier so
    # focused refinements can compete with the original broad pass
    # without having to beat the broad-pass score outright.  The raw
    # ``score.total >= 30.0`` floor still applies — we never keep
    # garbage just because it's a re-attempt.
    attempts = state.dimension_attempts.get(dimension, 0)
    depth_bonus = float(getattr(ctx.config.scoring.weights, "depth_bonus", 0.0))
    if depth_bonus > 0 and attempts >= 2:
        # Scale prev_best DOWN proportionally — equivalent to scaling
        # score.total UP, but easier to reason about in logs.
        # Cap multiplier growth at 1.45 (3 boosted attempts).
        depth_multiplier = 1.0 + depth_bonus * min(attempts - 1, 3)
        prev_best_for_keep = prev_best / depth_multiplier
    else:
        prev_best_for_keep = prev_best
    kept = score.total > prev_best_for_keep and score.total >= 30.0
    emitter.transition(
        ResearchState.DECIDE,
        iteration=state.iteration,
        dimension=dimension,
        status=IterationDecision.KEEP if kept else IterationDecision.DISCARD,
    )
    if kept:
        state.best_scores[dimension] = score.total
        if score.total > state.best_score:
            state.best_score = score.total
        _merge(ctx, state, dimension, findings, score)
        log.info("KEEP — merged into knowledge base.")
        emitter.transition(ResearchState.MERGE, iteration=state.iteration, dimension=dimension)
    else:
        log.info("DISCARD — findings saved but not merged.")
        _maybe_exhaust(state, dimension)

    _decision = IterationDecision.KEEP if kept else IterationDecision.DISCARD

    with ctx.audit_trail.step(
        "persist_iteration_markdown",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        dimension=dimension,
        status=_decision,
    ):
        write_iteration_markdown(
            iterations_dir=state.iterations_dir,
            iteration=state.iteration,
            dimension=dimension,
            findings=findings,
            score=score,
            kept=kept,
        )
    # Discovery plan Phase 2: persist the structured discovered_gaps
    # state to the sidecar after each iteration so --resume can restore
    # it without re-deriving from results.tsv.
    if state.discovered_gaps:
        try:
            from .run_io import write_discovered_gaps_sidecar
            write_discovered_gaps_sidecar(ctx.artifact_root, state.discovered_gaps)
        except Exception:
            log.debug("Failed to persist discovered_gaps sidecar", exc_info=True)
    ctx.collect_provenance(findings, scope=f"iteration-{state.iteration:03d}", dimension=dimension)
    _log_result(
        ctx, state, dimension, score, hypothesis.get("rationale", ""),
        status=_decision,
    )

    if state.iteration % ctx.config.execution.compress_every == 0:
        _compress_knowledge_base(ctx, state)

    ctx.audit_trail.emit(
        "iteration_completed",
        iteration=state.iteration,
        dimension=dimension,
        status=_decision,
        total_score=score.total,
    )

    state.current_workflow_state = emitter.current_state


def _generate_hypothesis(ctx: LoopContext, state: LoopState) -> dict[str, Any] | None:
    """Ask the agent to pick the next research dimension.

    Discovery plan Phase 4: refinement requests for already-explored
    dimensions are surfaced alongside unexplored dimensions so the
    hypothesis generator can pick "go deeper on X" as well as
    "explore Y".  The prompt template prefixes refinements with
    ``[refinement]`` so the model can distinguish them.
    """
    unexplored = [
        d for d in [*ctx.config.dimensions, *state.discovered_dimensions]
        if d not in state.explored_dimensions
    ]
    refinement_items = [f"[refinement] {topic}" for topic in state.refinement_requests]
    eligible = unexplored + refinement_items

    prompt = _render(
        "research_hypothesis.md",
        topic=ctx.config.topic,
        methodology=ctx.methodology_summary(),
        knowledge_summary=ctx.kb_summary(),
        explored_dimensions=ctx.format_dimension_list(state.explored_dimensions),
        unexplored_dimensions=ctx.format_dimension_list(eligible),
    )

    hypo_backend = ctx.strategy.get_hypothesis_backend()
    with ctx.audit_trail.step(
        "generate_hypothesis",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        backend=hypo_backend.name,
    ):
        resp = ctx.call_with(hypo_backend, prompt, max_turns=3)

    if resp.is_error or not resp.text:
        return None

    ctx.track_usage(resp, hypo_backend.name)

    try:
        return json.loads(resp.text)
    except json.JSONDecodeError:
        text = resp.text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        log.warning("Could not parse hypothesis JSON: %.200s", resp.text)
        return None


def _execute_research(
    ctx: LoopContext,
    state: LoopState,
    dimension: str,
    questions: list[str],
    approach: str,
) -> str:
    """Run a research agent on the given dimension."""
    formatted_questions = "\n".join(f"- {q}" for q in questions) if questions else "- Explore broadly"

    prompt = _render(
        "research.md",
        topic=ctx.config.topic,
        methodology=ctx.methodology_summary(),
        dimension=dimension,
        questions=formatted_questions,
        approach=approach or "Use web search and official documentation",
        knowledge_summary=ctx.kb_summary(),
    )

    kwargs: dict[str, Any] = {}
    if hasattr(ctx.strategy, "route_dimension"):
        kwargs["dimension"] = dimension

    with ctx.audit_trail.step(
        "execute_research",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        dimension=dimension,
        strategy=ctx.config.execution.strategy,
    ):
        result = ctx.strategy.execute_research(
            prompt,
            ctx.invoke_for_strategy,
            allowed_tools=ctx.config.execution.allowed_tools,
            max_turns=ctx.config.execution.max_turns,
            timeout=ctx.config.execution.timeout_seconds,
            **kwargs,
        )

    if result.candidates is not None:
        for candidate in result.candidates:
            ctx.track_candidate_usage(candidate)
    else:
        ctx.track_cost(result.cost_usd, result.backend_name)

    findings = result.findings
    if result.candidates and len(result.candidates) > 1:
        findings = _select_candidate_findings(ctx, state, dimension, result.candidates)
    elif result.candidates and len(result.candidates) == 1 and not findings:
        findings = result.candidates[0].findings

    if not findings:
        log.error("Research call failed.")
        _emit_research_failure_diagnosis(ctx, dimension)
        return ""

    with ctx.audit_trail.step(
        "post_research_critique",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        dimension=dimension,
    ):
        critique = ctx.strategy.post_research(
            findings, ctx.invoke_for_strategy,
            timeout=ctx.config.execution.timeout_seconds,
        )
    if critique:
        ctx.track_cost(critique.cost_usd, critique.backend_name)
        findings += (
            f"\n\n---\n\n## Peer Review ({critique.backend_name})\n\n"
            f"{critique.critique}"
        )

    return findings


def _emit_research_failure_diagnosis(ctx: LoopContext, dimension: str) -> None:
    """Emit a diagnosis artifact when a research call returns no findings.

    Uses the execution integration adapter so the failure is captured in the
    same structured way as implement-mode boundary violations.  The artifact
    is persisted to ``research_diagnosis.json`` under the run artifact root
    so operators can inspect it after the run.
    """
    try:
        import json as _json
        from .execution.integration import diagnose_research_failure
        artifact = diagnose_research_failure(dimension, ctx.artifact_root)
        log.warning(
            "[research][diagnosis] dimension=%r type=%s — %s",
            dimension, artifact.diagnosis_type, artifact.summary,
        )
        diag_path = ctx.artifact_root / "research_diagnosis.json"
        diag_path.parent.mkdir(parents=True, exist_ok=True)
        diag_path.write_text(
            _json.dumps(artifact.to_dict(), indent=2), encoding="utf-8"
        )
    except Exception:
        log.debug("[research][diagnosis] could not emit diagnosis artifact", exc_info=True)


def _select_candidate_findings(
    ctx: LoopContext,
    state: LoopState,
    dimension: str,
    candidates: list[ResearchCandidate],
) -> str:
    """Select or merge the best findings from multiple backend candidates."""
    if not candidates:
        return ""

    ranked = sorted(
        candidates,
        key=lambda c: heuristic_score(
            c.findings,
            ctx.config,
            state.explored_dimensions,
            target_dimension=dimension,
        ),
        reverse=True,
    )
    merge_mode = ctx.config.execution.strategy_config.merge_mode
    threshold = ctx.config.execution.strategy_config.merge_threshold

    if merge_mode == "union":
        selected: list[tuple[ResearchCandidate, IterationScore]] = []
        for candidate in ranked:
            score = _score(ctx, state, dimension, candidate.findings)
            state.candidate_assessments.append(CandidateAssessment(
                iteration=state.iteration, dimension=dimension,
                backend_name=candidate.backend_name,
                coverage=score.coverage, quality=score.quality, total=score.total,
            ))
            if score.total >= threshold:
                selected.append((candidate, score))
        if not selected:
            return ""
        selected.sort(key=lambda item: item[1].total, reverse=True)
        log.info(
            "Merged %d candidate findings above threshold %.1f for dimension '%s'.",
            len(selected), threshold, dimension,
        )
        return "\n\n---\n\n".join(
            f"<!-- source: {candidate.backend_name}; score: {score.total:.1f} -->\n{candidate.findings}"
            for candidate, score in selected
        )

    shortlist = ranked[: min(2, len(ranked))]
    best_candidate = shortlist[0]
    best_score = -1.0

    for candidate in shortlist:
        score = _score(ctx, state, dimension, candidate.findings)
        state.candidate_assessments.append(CandidateAssessment(
            iteration=state.iteration, dimension=dimension,
            backend_name=candidate.backend_name,
            coverage=score.coverage, quality=score.quality, total=score.total,
        ))
        if score.total > best_score:
            best_candidate = candidate
            best_score = score.total

    log.info(
        "Selected %s from %d candidates for dimension '%s' (score %.1f).",
        best_candidate.backend_name, len(candidates), dimension, best_score,
    )
    return best_candidate.findings


# --- Discovery plan Phase 1: gap intake processing ---------------------------

# A small set of Spanish-only stop-words covers the actual code-switch
# noise observed in the localstack run (the Gemini adversary occasionally
# emitted gaps starting with "Verificación de" / "Detalle de" / "Falta de"
# with several Spanish particles). When ``discovery.language_filter`` is
# ``"en"`` we drop any gap topic with two or more of these tokens — that
# threshold catches the observed Spanish noise without false-positives on
# English text that happens to include a single foreign loan-word.
_SPANISH_STOPWORDS = frozenset({
    "de", "la", "el", "los", "las", "una", "uno", "por", "con", "del",
    "para", "como", "que", "es", "en", "se", "lo", "al", "su", "sus",
    "y", "o", "pero", "este", "esta", "estos", "estas", "no",
})


def _looks_spanish(topic: str) -> bool:
    """Return True if ``topic`` reads as Spanish using a stop-word
    heuristic. Avoids the langdetect dependency for this minimal need.
    """
    tokens = re.findall(r"\b[a-záéíóúñü]+\b", topic.lower())
    if len(tokens) < 4:
        return False
    spanish_hits = sum(1 for t in tokens if t in _SPANISH_STOPWORDS)
    return spanish_hits >= 2


def _canonical_topic(topic: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation.
    Used as a hash for duplicate detection."""
    cleaned = re.sub(r"\s+", " ", topic.strip()).strip(".:;,!?\"'`")
    return cleaned.lower()


def _edit_distance_ratio(a: str, b: str) -> float:
    """Cheap Levenshtein-style similarity ratio in [0, 1]. Returns 1.0
    for identical strings, lower for divergent. Implementation uses
    difflib (stdlib) to avoid a new dependency."""
    from difflib import SequenceMatcher
    return SequenceMatcher(a=a, b=b).ratio()


_DEFAULT_DEDUPE_THRESHOLD = 0.85
_GAP_MIN_CHARS = 30
_GAP_MAX_CHARS = 200


def process_discovered_gaps(
    gap_records: list[dict[str, Any]],
    *,
    state: "LoopState",
    config: ResearchConfig,
    audit_trail: Any,
    iteration: int,
    dimension: str,
) -> list[dict[str, Any]]:
    """Filter judge-emitted gaps before they enter the discovered pool.

    Runs each gap through normalize → length → language → dedupe, and
    emits an audit-trail event for every rejected item so operators can
    inspect what was thrown out.

    The discovery config block is optional with safe defaults:

        discovery:
          language_filter: en | none   # default: en
          dedupe_threshold: 0.85       # Levenshtein ratio above which
                                       # two topics are considered the
                                       # same gap. Default 0.85.

    Returns the filtered list of structured gap records.
    """
    discovery_cfg = getattr(config, "discovery", None)
    language_filter = getattr(discovery_cfg, "language_filter", "en")
    dedupe_threshold = getattr(discovery_cfg, "dedupe_threshold", _DEFAULT_DEDUPE_THRESHOLD)

    existing_topics = [
        _canonical_topic(d) for d in (
            *config.dimensions,
            *state.discovered_dimensions,
        )
    ]

    accepted: list[dict[str, Any]] = []
    accepted_canonicals: list[str] = list(existing_topics)

    for raw in gap_records:
        topic = raw.get("topic", "").strip()
        if not topic:
            continue
        canonical = _canonical_topic(topic)
        record = {**raw, "canonical_topic": canonical}

        # Length filter
        if len(topic) < _GAP_MIN_CHARS:
            _audit_gap_filter(audit_trail, "too_short", record, iteration, dimension)
            continue
        if len(topic) > _GAP_MAX_CHARS:
            _audit_gap_filter(audit_trail, "too_long", record, iteration, dimension)
            continue

        # Language filter
        if language_filter == "en" and _looks_spanish(topic):
            _audit_gap_filter(audit_trail, "non_english", record, iteration, dimension)
            continue

        # Dedupe filter (against configured + already-discovered + already-
        # accepted-this-call topics, using edit-distance similarity).
        is_dup = False
        for prior in accepted_canonicals:
            if not prior:
                continue
            if canonical == prior or _edit_distance_ratio(canonical, prior) >= dedupe_threshold:
                _audit_gap_filter(
                    audit_trail, "duplicate", record, iteration, dimension,
                    extra={"matched_topic": prior},
                )
                is_dup = True
                break
        if is_dup:
            continue

        accepted.append(record)
        accepted_canonicals.append(canonical)

    return accepted


def _audit_gap_filter(
    audit_trail: Any,
    reason: str,
    record: dict[str, Any],
    iteration: int,
    dimension: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Record a gap-filter rejection in audit_trail.jsonl. Best-effort —
    if the audit trail doesn't expose the right method, swallow the
    error rather than blocking the score."""
    payload = {
        "iteration": iteration,
        "dimension": dimension,
        "reason": reason,
        "topic": record.get("topic", ""),
        "kind": record.get("kind", "research_target"),
        "confidence": record.get("confidence", 5),
    }
    if extra:
        payload.update(extra)
    try:
        emit = getattr(audit_trail, "emit", None)
        if callable(emit):
            # AuditTrailWriter.emit signature is emit(event, **fields).
            emit(f"gap_filtered_{reason}", **payload)
        else:
            log.debug("audit emit unavailable; gap_filtered_%s skipped: %s", reason, payload)
    except Exception:
        log.debug("Failed to record gap_filtered_%s audit event", reason, exc_info=True)


# --- end discovery intake ---------------------------------------------------


def _score(ctx: LoopContext, state: LoopState, dimension: str, findings: str) -> IterationScore:
    """Score findings using heuristics and an LLM judge.

    The heuristic component is computed in ``target_dimension`` mode so
    findings focused on the assigned dimension are scored on depth rather
    than breadth across the whole configured dimension list.
    """
    breakdown = heuristic_breakdown(
        findings,
        ctx.config,
        state.explored_dimensions,
        target_dimension=dimension,
    )
    coverage = breakdown.total

    quality = 50.0
    judge_raw: dict[str, Any] = {}

    try:
        prompt = _render(
            "research_evaluate.md",
            topic=ctx.config.topic,
            goal=ctx.config.goal,
            methodology=ctx.methodology_summary(),
            goal_constraints=ctx.goal_constraints_summary(),
            dimension=dimension,
            findings=findings[:_MAX_FINDINGS_CHARS],
            knowledge_summary=ctx.kb_summary(),
        )

        judge_backend = ctx.strategy.get_judge_backend()
        with ctx.audit_trail.step(
            "score_findings",
            artifact_root=ctx.artifact_root,
            iteration=state.iteration,
            dimension=dimension,
            backend=judge_backend.name,
        ):
            resp = ctx.call_with(judge_backend, prompt, max_turns=3)
        ctx.track_usage(resp, judge_backend.name)

        if not resp.is_error and resp.text:
            judge_raw = parse_judge_response(resp.text)
            quality = quality_score_from_judge(judge_raw)
    except Exception as exc:
        log.warning("Judge scoring failed, using fallback: %s", exc)

    # --- Scoring plan Phase 2: heuristic novelty against the KB ---
    # Always computed for visibility (log line, dashboard, results.tsv);
    # only enters the total when ``scoring.weights.novelty_weight > 0``.
    h_novelty = novelty_score(findings, state.knowledge_base)
    judge_novelty_axis = int(judge_raw.get("novelty", 0) or 0)

    total = combine_scores_weighted(
        coverage=coverage,
        quality=quality,
        judge_novelty_axis=judge_novelty_axis,
        heuristic_novelty=h_novelty,
        weights=ctx.config.scoring.weights,
    )

    # --- Discovery plan Phase 1: normalise + filter the judge's gaps ---
    raw_gap_records = parse_gaps_identified(judge_raw.get("gaps_identified", []))
    accepted_records = process_discovered_gaps(
        raw_gap_records,
        state=state,
        config=ctx.config,
        audit_trail=ctx.audit_trail,
        iteration=state.iteration,
        dimension=dimension,
    )
    accepted_topics = [r["topic"] for r in accepted_records]

    return IterationScore(
        coverage=coverage,
        quality=quality,
        total=total,
        dimensions_covered=judge_raw.get("dimensions_covered", [dimension]),
        gaps=accepted_topics,
        gap_records=accepted_records,
        judge_raw=judge_raw,
        heuristic_breakdown=breakdown,
        judge_depth=int(judge_raw.get("depth", 0) or 0),
        judge_accuracy=int(judge_raw.get("accuracy", 0) or 0),
        judge_novelty=judge_novelty_axis,
        judge_actionability=int(judge_raw.get("actionability", 0) or 0),
        heuristic_novelty=h_novelty,
    )


def _merge(ctx: LoopContext, state: LoopState, dimension: str, findings: str, score: IterationScore) -> None:
    """Merge kept findings into the knowledge base."""
    with ctx.audit_trail.step(
        "merge_findings",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        dimension=dimension,
    ):
        merged = merge_findings(
            dimension=dimension,
            findings=findings,
            gaps=score.gaps,
            knowledge_base=state.knowledge_base,
            explored_dimensions=state.explored_dimensions,
            discovered_dimensions=state.discovered_dimensions,
            configured_dimensions=ctx.config.dimensions,
        )
        state.knowledge_base = merged["knowledge_base"]
        state.explored_dimensions = merged["explored_dimensions"]
        state.discovered_dimensions = merged["discovered_dimensions"]
        state.kb_path.write_text(state.knowledge_base, encoding="utf-8")

        # Discovery plan Phase 2: persist structured gap metadata
        # alongside the bare-string view.  Each surviving record from
        # intake either creates a new GapEntry (gap_promoted audit
        # event) or increments an existing one (gap_seen_again event).
        judge_name = getattr(ctx.strategy.get_judge_backend(), "name", "")
        discovery_cfg = getattr(ctx.config, "discovery", None)
        promotion_enabled = bool(getattr(discovery_cfg, "promotion_enabled", False))
        promotion_min_occ = int(getattr(discovery_cfg, "promotion_min_occurrences", 2))
        promotion_high_conf = int(getattr(discovery_cfg, "promotion_high_confidence", 8))
        for record in score.gap_records:
            canonical = record.get("canonical_topic") or _canonical_topic(record["topic"])
            entry, is_new = record_gap(
                discovered_gaps=state.discovered_gaps,
                discovered_dimensions=state.discovered_dimensions,
                canonical_topic=canonical,
                display_topic=record["topic"],
                iteration=state.iteration,
                judge_name=judge_name,
                kind=record.get("kind", "research_target"),
                confidence=record.get("confidence", 5),
                promotion_enabled=promotion_enabled,
                promotion_min_occurrences=promotion_min_occ,
                promotion_high_confidence=promotion_high_conf,
            )
            if is_new:
                _emit_audit(ctx.audit_trail, "gap_promoted", {
                    "iteration": state.iteration,
                    "dimension": dimension,
                    "canonical_topic": canonical,
                    "display_topic": entry.display_topic,
                    "kind": entry.kind,
                    "confidence": record.get("confidence", 5),
                })
            else:
                _emit_audit(ctx.audit_trail, "gap_seen_again", {
                    "iteration": state.iteration,
                    "dimension": dimension,
                    "canonical_topic": canonical,
                    "occurrences": entry.occurrences,
                })
        for gap in score.gaps:
            if gap in state.discovered_dimensions:
                log.info("New dimension discovered: %s", gap)

        # Discovery plan Phase 4: refresh kind-based views.  Refinement
        # requests and critiques become observable to the hypothesis
        # generator and the synthesis report respectively.
        rebuild_kind_views(state)
        if state.refinement_requests:
            log.info(
                "Refinement requests open: %d (e.g. %r)",
                len(state.refinement_requests), state.refinement_requests[0][:80],
            )
        if state.critiques:
            log.info("Open critiques: %d", len(state.critiques))


def rebuild_kind_views(state: "LoopState") -> None:
    """Discovery plan Phase 4: refresh per-kind views over discovered_gaps.

    - ``state.discovered_dimensions``: promoted research_target topics
      (the original list, kept in sync separately by record_gap so we
      don't rewrite it here).
    - ``state.refinement_requests``: promoted refinement topics —
      target existing explored dimensions for re-investigation.
      Consumed by the hypothesis prompt to suggest "go deeper on X".
    - ``state.critiques``: every critique-kind gap with its full
      structured metadata.  Stored for the synthesis report;
      never enters the hypothesis pool.
    """
    refinement_topics: list[str] = []
    critique_records: list[dict[str, Any]] = []
    for entry in state.discovered_gaps.values():
        if entry.kind == "refinement" and entry.promoted:
            if entry.display_topic not in refinement_topics:
                refinement_topics.append(entry.display_topic)
        elif entry.kind == "critique":
            critique_records.append({
                "topic": entry.display_topic,
                "canonical_topic": entry.canonical_topic,
                "occurrences": entry.occurrences,
                "iterations_seen": list(entry.iterations_seen),
                "judges_seen": list(entry.judges_seen),
                "confidence_mean": (
                    sum(entry.confidences) / len(entry.confidences)
                    if entry.confidences else 0.0
                ),
            })
    state.refinement_requests = refinement_topics
    state.critiques = critique_records


def _emit_audit(audit_trail: Any, event_type: str, payload: dict[str, Any]) -> None:
    """Best-effort audit event emit; swallows errors so audit issues
    never block the research loop.

    AuditTrailWriter.emit() takes the event type as a positional arg
    and any structured fields as keyword args, so we splat the payload.
    """
    try:
        emit = getattr(audit_trail, "emit", None)
        if callable(emit):
            emit(event_type, **payload)
    except Exception:
        log.debug("Failed to emit audit event %s", event_type, exc_info=True)


def _maybe_exhaust(state: LoopState, dimension: str) -> None:
    """Mark a dimension as explored if it has reached max attempts."""
    exhausted = maybe_exhaust_dimension(
        dimension=dimension,
        dimension_attempts=state.dimension_attempts,
        explored_dimensions=state.explored_dimensions,
        max_attempts_per_dimension=state.MAX_ATTEMPTS_PER_DIMENSION,
    )
    if exhausted:
        log.info(
            "Dimension exhausted after %d attempts, moving on: %s",
            state.MAX_ATTEMPTS_PER_DIMENSION, dimension,
        )


def _log_result(
    ctx: LoopContext,
    state: LoopState,
    dimension: str,
    score: IterationScore,
    hypothesis: str,
    *,
    status: str,
) -> None:
    """Append a row to results.tsv for this iteration."""
    with ctx.audit_trail.step(
        "append_results_row",
        artifact_root=ctx.artifact_root,
        iteration=state.iteration,
        dimension=dimension,
        status=status,
    ):
        row = build_result_row(
            iteration=state.iteration,
            dimension=dimension,
            score=score,
            hypothesis=hypothesis,
            status=status,
            total_cost_usd=state.total_cost,
            total_input_tokens=state.total_input_tokens,
            total_output_tokens=state.total_output_tokens,
        )
        state.results.append(row)
        append_result_row(state.results_path, row)


# Memory needed to safely invoke a CLI-backed compress: claude-cli's Node heap
# baseline (~1.5 GB) plus python framework headroom plus a margin. Below this,
# the kernel is likely to SIGKILL the python process during the subprocess
# spawn. Tunable via env var for ops who want to override on bigger machines.
_COMPRESS_MIN_FREE_GB = 2.0


def _available_memory_gb() -> float | None:
    """Return free system memory in GB, or None when detection fails.

    Resilience layers, in order: (1) psutil if installed (cross-platform);
    (2) ``vm_stat`` parsing on macOS; (3) ``/proc/meminfo`` on Linux.
    Returning None means "unknown" — the caller treats it as "don't block
    the operation on a measurement we can't make".
    """
    try:
        import psutil  # declared in pyproject.toml; this guard is for stale venvs

        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        pass

    import sys

    if sys.platform == "darwin":
        try:
            import subprocess

            out = subprocess.check_output(["vm_stat"], text=True, timeout=2)
            page_size = 16384  # macOS default on Apple Silicon; close enough on Intel
            free_pages = 0
            for line in out.splitlines():
                if line.startswith(("Pages free:", "Pages inactive:", "Pages speculative:")):
                    free_pages += int(line.rsplit(maxsplit=1)[-1].rstrip("."))
            return (free_pages * page_size) / (1024**3)
        except Exception:  # noqa: BLE001 — measurement, never raise
            return None

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / (1024**2)  # kB → GB
        except Exception:  # noqa: BLE001
            return None

    return None


def _truncate_knowledge_base(state: LoopState, reason: str) -> None:
    """Lossy fallback: keep the head + tail, drop the middle.

    Used when LLM-based compression cannot run (memory pressure) or fails
    (backend error, empty response). Lossy but bounded — the run continues
    instead of dying with a corpus that grows unbounded.
    """
    words = state.knowledge_base.split()
    if len(words) <= state.KB_MAX_WORDS:
        return

    head_size = state.KB_MAX_WORDS // 2
    tail_size = state.KB_MAX_WORDS - head_size
    head = " ".join(words[:head_size])
    tail = " ".join(words[-tail_size:])
    omitted = len(words) - state.KB_MAX_WORDS

    state.knowledge_base = (
        f"{head}\n\n"
        f"[... {omitted} words trimmed by lossy fallback ({reason}) ...]\n\n"
        f"{tail}"
    )
    state.kb_path.write_text(state.knowledge_base, encoding="utf-8")
    log.info(
        "Knowledge base truncated to %d words (lossy fallback: %s).",
        len(state.knowledge_base.split()),
        reason,
    )


def _compress_knowledge_base(ctx: LoopContext, state: LoopState) -> None:
    """Distill the knowledge base if it exceeds the word limit.

    Two-layer defense against OOM:
      1. PREVENT — pre-flight memory check refuses to invoke the compress
         backend when free RAM is below ``_COMPRESS_MIN_FREE_GB``. The CLI
         backends spawn a Node subprocess (~1.5 GB heap baseline); below
         the threshold, the kernel is likely to SIGKILL python during
         the spawn. Falls back to truncation.
      2. GRACEFUL DEGRADE — wraps the backend call so any error (timeout,
         empty response, exception) falls back to truncation rather than
         leaving the corpus uncompressed (which would make the *next*
         compress attempt even larger and more likely to OOM).

    SIGKILL during the backend call cannot be caught — but layer 1 makes
    that case rare, and on resume the run picks up at the post-truncation
    state if the previous attempt fell through to layer 2.
    """
    word_count = len(state.knowledge_base.split())
    if word_count <= state.KB_MAX_WORDS:
        return

    # Layer 1: pre-flight memory guard.
    free_gb = _available_memory_gb()
    if free_gb is not None and free_gb < _COMPRESS_MIN_FREE_GB:
        log.warning(
            "Skipping LLM compress at iter %d: only %.2f GB free (need %.1f GB). "
            "Falling back to truncation.",
            state.iteration, free_gb, _COMPRESS_MIN_FREE_GB,
        )
        ctx.audit_trail.emit(
            "compress_skipped_low_memory",
            iteration=state.iteration,
            free_gb=round(free_gb, 2),
            threshold_gb=_COMPRESS_MIN_FREE_GB,
            corpus_words=word_count,
        )
        _truncate_knowledge_base(state, reason="low memory pre-flight")
        return

    log.info(
        "Compressing knowledge base (%d words -> target %d)...",
        word_count, state.KB_MAX_WORDS,
    )

    prompt = (
        "Distill the following research findings into a concise summary. "
        "Preserve all key facts, numbers, comparisons, and trade-offs. "
        "Remove redundancy and filler. Target length: ~3000 words.\n\n"
        f"{state.knowledge_base}"
    )

    # Layer 2: try the LLM compress, fall through to truncation on any failure.
    compress_backend = ctx.strategy.get_compress_backend()
    try:
        with ctx.audit_trail.step(
            "compress_knowledge_base",
            artifact_root=ctx.artifact_root,
            iteration=state.iteration,
            backend=compress_backend.name,
        ):
            resp = ctx.call_with(compress_backend, prompt, max_turns=3, timeout=120)
        ctx.track_usage(resp, compress_backend.name)
    except Exception as exc:  # noqa: BLE001 — never let compress kill the run
        log.warning(
            "Compress raised %s at iter %d; falling back to truncation.",
            exc.__class__.__name__, state.iteration,
        )
        ctx.audit_trail.emit(
            "compress_failed_fallback_truncate",
            iteration=state.iteration,
            error=f"{exc.__class__.__name__}: {exc}",
            corpus_words=word_count,
        )
        _truncate_knowledge_base(state, reason=f"compress raised {exc.__class__.__name__}")
        return

    if not resp.is_error and resp.text and len(resp.text) > 200:
        state.knowledge_base = resp.text
        state.kb_path.write_text(state.knowledge_base, encoding="utf-8")
        log.info("Knowledge base compressed to %d words.", len(resp.text.split()))
    else:
        log.warning(
            "Compress returned empty/error at iter %d; falling back to truncation.",
            state.iteration,
        )
        ctx.audit_trail.emit(
            "compress_failed_fallback_truncate",
            iteration=state.iteration,
            error="empty_or_error_response",
            corpus_words=word_count,
        )
        _truncate_knowledge_base(state, reason="compress returned empty/error")
