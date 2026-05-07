"""Runtime state helpers for the autoresearch loop."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .backends import AgentResponse
from .strategy import ResearchCandidate
from .workflows.decisions import IterationDecision, classify_iteration_decision


# ---------------------------------------------------------------------------
# Discovery plan Phase 2: persistent gap state
# ---------------------------------------------------------------------------


@dataclass
class GapEntry:
    """Structured record for a single discovered gap.

    Replaces the bare-string entries in the legacy
    ``state.discovered_dimensions: list[str]`` with the metadata needed
    by Discovery plan Phase 3 (clustering with re-discovery promotion)
    and Phase 4 (kind-based dispatch).  Phase 2 just lays the schema —
    every gap that survives the intake filter creates an entry, and
    the entry's ``occurrences`` count is incremented when the same
    canonical_topic is recorded again from a later iteration.

    Attributes:
        canonical_topic: Normalised form used for matching (lowercased,
            whitespace-collapsed, punctuation-stripped).  This is the
            key in ``state.discovered_gaps``.
        display_topic: Most recent display form (preserves casing,
            punctuation).  This is what gets fed to the hypothesis
            prompt's ``{unexplored_dimensions}`` placeholder.
        first_seen_iter: Iteration number when this canonical_topic
            first appeared.
        occurrences: How many distinct iterations have produced this
            gap.  Phase 3 will use this for re-discovery promotion.
        iterations_seen: Per-iteration log; the index into the
            iteration corpus where each occurrence happened.
        judges_seen: Backend names of the judges that emitted this gap.
            Phase 3 cross-judge promotion uses this.
        kind: One of GAP_KINDS — ``research_target``, ``refinement``,
            or ``critique``.
        confidences: Per-occurrence confidence scores (1-10 each) from
            the judge.  Mean confidence is a Phase 3 promotion signal.
        promoted: Whether this gap is currently eligible to feed back
            into the hypothesis pool.  Phase 2 promotes everything
            that passes intake; Phase 3 will gate this.
    """

    canonical_topic: str
    display_topic: str
    first_seen_iter: int
    occurrences: int = 1
    iterations_seen: list[int] = field(default_factory=list)
    judges_seen: list[str] = field(default_factory=list)
    kind: str = "research_target"
    confidences: list[int] = field(default_factory=list)
    promoted: bool = True


def record_gap(
    *,
    discovered_gaps: dict[str, GapEntry],
    discovered_dimensions: list[str],
    canonical_topic: str,
    display_topic: str,
    iteration: int,
    judge_name: str = "",
    kind: str = "research_target",
    confidence: int = 5,
    promotion_min_occurrences: int = 2,
    promotion_high_confidence: int = 8,
    promotion_enabled: bool = False,
) -> tuple[GapEntry, bool]:
    """Add or update a discovered gap.

    Mutates ``discovered_gaps`` and ``discovered_dimensions`` in place
    so the legacy list-of-strings view stays in sync with the new
    dict-of-GapEntry source of truth.

    **Promotion (Discovery plan Phase 3).**  When ``promotion_enabled``
    is True, ``GapEntry.promoted`` is computed dynamically from
    convergence signal:

      promoted = (
        occurrences >= promotion_min_occurrences
        OR (kind == "refinement" AND occurrences >= 1)
        OR (occurrences == 1 AND mean(confidences) >= promotion_high_confidence)
      )

    Only promoted gaps appear in ``discovered_dimensions`` (the list
    consumed by the hypothesis prompt).  When ``promotion_enabled`` is
    False (the default), every gap is auto-promoted on first sight —
    matching pre-Phase-3 behavior.

    Returns ``(entry, is_new)`` — ``is_new`` is ``True`` when this
    canonical_topic was added for the first time, ``False`` when an
    existing entry was updated.
    """
    existing = discovered_gaps.get(canonical_topic)
    if existing is not None:
        existing.occurrences += 1
        if iteration not in existing.iterations_seen:
            existing.iterations_seen.append(iteration)
        if judge_name and judge_name not in existing.judges_seen:
            existing.judges_seen.append(judge_name)
        existing.confidences.append(confidence)
        # Most-recent display form wins.
        existing.display_topic = display_topic
        # Re-evaluate promotion with the updated counters.  Once
        # promoted a gap stays promoted (avoids surprising drops if a
        # later judge emits low confidence for an established topic).
        if promotion_enabled and not existing.promoted:
            existing.promoted = _evaluate_promotion(
                occurrences=existing.occurrences,
                kind=existing.kind,
                confidences=existing.confidences,
                min_occurrences=promotion_min_occurrences,
                high_confidence=promotion_high_confidence,
            )
            if existing.promoted and existing.display_topic not in discovered_dimensions:
                discovered_dimensions.append(existing.display_topic)
        return existing, False

    if promotion_enabled:
        promoted = _evaluate_promotion(
            occurrences=1,
            kind=kind,
            confidences=[confidence],
            min_occurrences=promotion_min_occurrences,
            high_confidence=promotion_high_confidence,
        )
    else:
        promoted = True

    entry = GapEntry(
        canonical_topic=canonical_topic,
        display_topic=display_topic,
        first_seen_iter=iteration,
        occurrences=1,
        iterations_seen=[iteration],
        judges_seen=[judge_name] if judge_name else [],
        kind=kind,
        confidences=[confidence],
        promoted=promoted,
    )
    discovered_gaps[canonical_topic] = entry
    if promoted and display_topic not in discovered_dimensions:
        discovered_dimensions.append(display_topic)
    return entry, True


def _evaluate_promotion(
    *,
    occurrences: int,
    kind: str,
    confidences: list[int],
    min_occurrences: int = 2,
    high_confidence: int = 8,
) -> bool:
    """Decide whether a gap is eligible for the hypothesis pool.

    Three positive paths:

    - ``occurrences >= min_occurrences`` — repeated across iterations
      is the strongest convergence signal.
    - ``kind == "refinement"`` — refinement requests target the
      *current* dimension and don't need to wait for cross-iteration
      confirmation.  A single sighting is enough.
    - ``occurrences == 1 AND mean(confidences) >= high_confidence`` —
      one-shot insight that the judge marked highly confident.
    """
    if occurrences >= min_occurrences:
        return True
    if kind == "refinement" and occurrences >= 1:
        return True
    if occurrences == 1 and confidences:
        mean_conf = sum(confidences) / len(confidences)
        if mean_conf >= high_confidence:
            return True
    return False


def serialise_discovered_gaps(gaps: dict[str, GapEntry]) -> dict[str, dict[str, Any]]:
    """Convert the dict-of-GapEntry to a JSON-serialisable form for the
    sidecar file."""
    return {topic: asdict(entry) for topic, entry in gaps.items()}


def deserialise_discovered_gaps(payload: dict[str, dict[str, Any]]) -> dict[str, GapEntry]:
    """Reconstruct the dict-of-GapEntry from a sidecar JSON payload.
    Tolerates missing fields (uses GapEntry defaults) and skips entries
    whose value isn't a dict, so legacy or partial sidecars don't
    crash resume."""
    result: dict[str, GapEntry] = {}
    for topic, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        try:
            result[topic] = GapEntry(
                canonical_topic=raw.get("canonical_topic", topic),
                display_topic=raw.get("display_topic", topic),
                first_seen_iter=int(raw.get("first_seen_iter", 0)),
                occurrences=int(raw.get("occurrences", 1)),
                iterations_seen=list(raw.get("iterations_seen", [])),
                judges_seen=list(raw.get("judges_seen", [])),
                kind=raw.get("kind", "research_target"),
                confidences=list(raw.get("confidences", [])),
                promoted=bool(raw.get("promoted", True)),
            )
        except (TypeError, ValueError, AttributeError):
            continue
    return result


@dataclass
class BaseContext:
    """Shared callback bundle for research and document loops.

    Both ``LoopContext`` (research mode) and ``CycleContext`` (document mode)
    extend this class. When orchestrator callback signatures change, only
    ``BaseContext`` needs updating.
    """

    call_with: Callable[..., AgentResponse]
    invoke_for_strategy: Callable[..., AgentResponse]
    track_usage: Callable[..., None]
    track_cost: Callable[..., None]


@dataclass
class UsageTotals:
    """Mutable usage/accounting state for a run."""

    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    per_backend_costs: dict[str, float] = field(default_factory=dict)
    per_backend_tokens: dict[str, dict[str, int]] = field(default_factory=dict)


def track_cost(usage: UsageTotals, cost: float, backend_name: str = "") -> None:
    """Add cost to totals."""
    usage.total_cost += cost
    if backend_name:
        usage.per_backend_costs[backend_name] = usage.per_backend_costs.get(backend_name, 0.0) + cost


def track_usage(usage: UsageTotals, resp: AgentResponse, backend_name: str = "") -> None:
    """Add cost and token counts to totals and per-backend tracking."""
    track_cost(usage, resp.cost_usd, backend_name)
    usage.total_input_tokens += resp.input_tokens
    usage.total_output_tokens += resp.output_tokens
    if backend_name:
        entry = usage.per_backend_tokens.setdefault(backend_name, {"input": 0, "output": 0})
        entry["input"] += resp.input_tokens
        entry["output"] += resp.output_tokens


def track_candidate_usage(usage: UsageTotals, candidate: ResearchCandidate) -> None:
    """Record usage for a strategy-produced research candidate."""
    track_usage(
        usage,
        AgentResponse(
            text=candidate.findings,
            cost_usd=candidate.cost_usd,
            is_error=False,
            input_tokens=candidate.input_tokens,
            output_tokens=candidate.output_tokens,
        ),
        candidate.backend_name,
    )


def resume_state(
    *,
    iterations_dir: Path,
    results_path: Path,
    knowledge_base_path: Path,
    configured_dimensions: tuple[str, ...] | list[str],
    max_attempts_per_dimension: int,
    discovered_gaps_sidecar: Path | None = None,
) -> dict[str, Any]:
    """Rebuild mutable state from existing iteration files and TSV.

    When ``discovered_gaps_sidecar`` is supplied AND the file exists,
    structured ``GapEntry`` records are loaded from it.  Otherwise the
    legacy fallback parses the ``discovered_gaps`` column from
    ``results.tsv`` and synthesises ``GapEntry`` records with
    conservative defaults — preserving ``--resume`` from runs that
    pre-date the schema upgrade.
    """
    existing = sorted(iterations_dir.glob("iter_*.md"))
    if not existing:
        return {
            "iteration": 0,
            "results": [],
            "best_score": 0.0,
            "best_scores": {},
            "explored_dimensions": [],
            "discovered_dimensions": [],
            "discovered_gaps": {},
            "dimension_attempts": {},
            "knowledge_base": knowledge_base_path.read_text(encoding="utf-8") if knowledge_base_path.exists() else "",
        }

    results: list[dict[str, str]] = []
    best_score = 0.0
    best_scores: dict[str, float] = {}
    explored_dimensions: list[str] = []
    discovered_dimensions: list[str] = []
    discovered_gaps: dict[str, GapEntry] = {}
    dimension_attempts: dict[str, int] = {}

    # Try the sidecar first.  Sidecar is authoritative when present.
    sidecar_loaded = False
    if discovered_gaps_sidecar and discovered_gaps_sidecar.exists():
        try:
            payload = json.loads(discovered_gaps_sidecar.read_text(encoding="utf-8"))
            discovered_gaps = deserialise_discovered_gaps(payload)
            discovered_dimensions = [entry.display_topic for entry in discovered_gaps.values()]
            sidecar_loaded = True
        except (json.JSONDecodeError, OSError, TypeError):
            sidecar_loaded = False

    if results_path.exists():
        with open(results_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                results.append(dict(row))
                dim = row.get("dimension", "")
                status = row.get("status", "")

                if dim:
                    dimension_attempts[dim] = dimension_attempts.get(dim, 0) + 1

                decision = classify_iteration_decision(status, default=IterationDecision.DISCARD)
                if decision == IterationDecision.KEEP:
                    try:
                        score = float(row.get("total_score", 0))
                    except (ValueError, TypeError):
                        score = 0.0

                    if dim:
                        if score > best_scores.get(dim, 0.0):
                            best_scores[dim] = score
                        if dim not in explored_dimensions:
                            explored_dimensions.append(dim)

                    if score > best_score:
                        best_score = score

                # Legacy fallback: synthesise GapEntry records from the
                # discovered_gaps TSV column when the sidecar wasn't
                # available.  Sidecar runs skip this branch entirely.
                if not sidecar_loaded:
                    gaps_raw = row.get("discovered_gaps", "")
                    if gaps_raw:
                        try:
                            gaps = json.loads(gaps_raw)
                        except (json.JSONDecodeError, TypeError):
                            gaps = []
                        try:
                            iter_num = int(row.get("iteration", "0"))
                        except (ValueError, TypeError):
                            iter_num = 0
                        for gap in gaps:
                            if (
                                gap
                                and gap not in explored_dimensions
                                and gap not in configured_dimensions
                                and gap not in discovered_dimensions
                            ):
                                discovered_dimensions.append(gap)
                                # Also synthesise a GapEntry so Phase 3+
                                # consumers see something even on legacy
                                # resume.  Conservative defaults:
                                # confidence=5, kind=research_target,
                                # promoted=True.
                                # Use lazy canonical-topic computation —
                                # avoids importing the full helper here.
                                from .research_loop import _canonical_topic
                                canonical = _canonical_topic(gap)
                                if canonical not in discovered_gaps:
                                    discovered_gaps[canonical] = GapEntry(
                                        canonical_topic=canonical,
                                        display_topic=gap,
                                        first_seen_iter=iter_num,
                                        occurrences=1,
                                        iterations_seen=[iter_num] if iter_num else [],
                                        judges_seen=[],
                                        kind="research_target",
                                        confidences=[5],
                                        promoted=True,
                                    )

                if dim and dimension_attempts.get(dim, 0) >= max_attempts_per_dimension:
                    if dim not in explored_dimensions:
                        explored_dimensions.append(dim)

    knowledge_base = knowledge_base_path.read_text(encoding="utf-8") if knowledge_base_path.exists() else ""
    return {
        "iteration": len(existing),
        "results": results,
        "best_score": best_score,
        "best_scores": best_scores,
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
        "discovered_gaps": discovered_gaps,
        "dimension_attempts": dimension_attempts,
        "knowledge_base": knowledge_base,
    }


def merge_findings(
    *,
    dimension: str,
    findings: str,
    gaps: list[str],
    knowledge_base: str,
    explored_dimensions: list[str],
    discovered_dimensions: list[str],
    configured_dimensions: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Merge kept findings into the knowledge base and update dimension
    tracking.

    The ``gaps`` list is a backward-compatible bare-string interface;
    callers that want the structured ``discovered_gaps`` dict updated
    in lock-step should call :func:`record_gap` directly instead of
    relying on this function to populate metadata.  When called via
    the legacy bare-string path, this function only updates
    ``discovered_dimensions`` — the structured dict is left to the
    caller.
    """
    if dimension not in explored_dimensions:
        explored_dimensions.append(dimension)

    # Idempotency guard: if a prior partial run already appended this
    # dimension's section to the KB on disk and then crashed between the
    # ``kb_path.write_text`` call and the ``write_iteration_markdown`` /
    # ``append_results_row`` calls, the resume path will rerun this
    # iteration with the same dimension (because ``explored_dimensions``
    # was rebuilt from ``results.tsv``, which never got the row).  Without
    # this check, the LLM-produced findings would be appended a second
    # time, doubling the dimension's content in the knowledge base.
    #
    # Prepend a newline before the search so first-line section headers
    # also match the marker pattern (matters when KB has been compressed
    # down to a single section that starts at position 0).
    dim_section_marker = f"\n## {dimension}\n"
    skipped_duplicate_merge = dim_section_marker in ("\n" + knowledge_base)

    if not skipped_duplicate_merge:
        knowledge_base += f"\n\n## {dimension}\n\n" + findings

    for gap in gaps:
        if (
            gap not in explored_dimensions
            and gap not in configured_dimensions
            and gap not in discovered_dimensions
        ):
            discovered_dimensions.append(gap)

    return {
        "knowledge_base": knowledge_base,
        "explored_dimensions": explored_dimensions,
        "discovered_dimensions": discovered_dimensions,
        "skipped_duplicate_merge": skipped_duplicate_merge,
    }


def maybe_exhaust_dimension(
    *,
    dimension: str,
    dimension_attempts: dict[str, int],
    explored_dimensions: list[str],
    max_attempts_per_dimension: int,
) -> bool:
    """Mark a dimension as explored if it has reached max attempts."""
    if dimension_attempts.get(dimension, 0) >= max_attempts_per_dimension:
        if dimension not in explored_dimensions:
            explored_dimensions.append(dimension)
        return True
    return False
