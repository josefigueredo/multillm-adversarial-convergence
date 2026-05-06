# Scoring Enhancements Plan

> **Status: ✅ COMPLETED** (2026-05-06)
>
> All 8 proposals implemented and tested.  Per-proposal commits:
>
> - #1 target-dimension coverage → `dd843a9` (Phase 1)
> - #2 novelty signal → `271a622` (Phase 2)
> - #3 surface components → `dd843a9` (Phase 1)
> - #4 multi-judge consensus → `db9c36f` (Phase 4)
> - #5 per-dim evidence types → **OBSOLETED** by the universal-signal
>   redesign in `f433cd6` (operators no longer need to author per-dim
>   `expected_evidence` lists; universal signals work across all
>   dimension types)
> - #6 length curve → `dd843a9` (Phase 1)
> - #7 cost-per-dollar dashboard view → `db9c36f` (Phase 4)
> - #8 cross-iteration depth bonus → `c81eb18` (shipped with Discovery
>   Phase 4)
>
> Configuration (all opt-in via YAML; defaults preserve legacy behavior):
>
> ```yaml
> research:
>   scoring:
>     weights:
>       novelty_weight: 0.25      # blends novelty into total
>       depth_bonus: 0.15         # eases re-attempts past prev_best
>   evaluation:
>     judges:
>       - adapter: gemini-cli
>         weight: 1.0
>       - adapter: codex-cli
>         weight: 1.0
> ```
>
> See `configs/research/_template.yaml` for the full annotated schema
> and `AGENTS.md` for operator-facing summaries of new audit events
> and dashboard fields.

Concrete plan to fix bias in the research-mode scoring pipeline and add
the observability needed to keep iterating on it. Grounded in evidence
from the `localstack_alternatives_copilot_gemini` run on 2026-05-06.

## Context

The current scoring pipeline (`src/scorer.py` + `src/research_loop.py`)
combines a deterministic heuristic (40%) with an LLM-judge call (60%):

```
total = 0.4 * coverage + 0.6 * quality
```

A finding is KEPT iff `total > prev_best AND total >= 30.0`, where
`prev_best` is the best prior score for the *same* dimension.

### What the run revealed

A 6-iteration adversarial research run produced these scores:

| Iter | Dimension | Coverage | Quality | Total | KEPT? |
|---|---|---|---|---|---|
| 1 | Migration effort (broad survey) | 85.0 | 75.0 | **79.0** | yes |
| 2 | CI/CD integration | 58.8 | 75.0 | 68.5 | yes |
| 3 | Terraform/CDK/SAM | 50.0 | 67.5 | 60.5 | yes |
| 4 | AWS service coverage | 67.5 | 60.0 | 63.0 | yes |
| 5 | Community / maintenance | 50.0 | 57.5 | 54.5 | yes |
| 6 | Licensing / pricing | 76.2 | 65.0 | 69.5 | yes |

Every iteration was kept. But iter 1 (a broad first pass) set a
high-water mark that focused later iterations couldn't approach,
despite the framework explicitly instructing them to focus on a single
dimension. That asymmetry surfaces three structural problems:

1. **The coverage heuristic rewards breadth, not depth**, even when the
   iteration is asked to focus. Iter 2-6 were *correct behavior* getting
   penalised as if they were incomplete.
2. **There is no novelty signal in the heuristic.** Restating known
   knowledge_base content scores the same as introducing genuinely new
   evidence, so the model has no incentive to push past the corpus.
3. **The judge is one LLM with one bias.** Gemini ran 60-75 on quality;
   a different judge would have produced different numbers. Single-judge
   variance is invisible to operators.

Plus four secondary issues the code review surfaced:

4. **Score components are hidden.** Operators see `coverage: 60.5,
   quality: 67.5, total: 64.7` but can't tell *why* coverage was 60 —
   was it short findings? missing evidence types? off-topic content?
5. **Evidence-type weighting is global**, but different dimensions need
   different evidence (Licensing needs `pricing_data`, Migration needs
   `code_example`, Community needs commit-frequency stats that aren't
   in the default catalog at all).
6. **Word count rewards length linearly up to a cap**, incentivising
   padding. Real value from research is information density, not bulk.
7. **Cross-iteration depth is structurally hard.** Once a dimension
   scores 79.0 broadly, refining it requires beating 79.0 with the same
   breadth-biased scorer. The heuristic actively discourages depth.

## Goals

- Make per-iteration scores reflect the framework's actual instruction
  to the model (focus on the target dimension), not a generic
  "covered everything" rubric.
- Add a novelty signal so iteration N is rewarded for adding what
  iteration N-1 didn't.
- Surface enough internal score detail for operators to debug without
  having to read source.
- Reduce single-judge bias as an operator-controlled option.
- Allow per-dimension calibration of what "good evidence" looks like.

## Non-goals

- Changing the `IterationScore` public field set in a way that breaks
  existing artifact consumers. New fields are additive only.
- Replacing the heuristic+judge composition with something fundamentally
  different (e.g., pure LLM scoring). The composition is a deliberate
  trade-off and stays.
- Calibrating against a benchmark catalog. The catalog
  (`benchmark_catalog/`) exists but its rubric is shallow today; that
  deserves its own plan.
- Touching the KEEP gate's `>= 30.0` minimum. Currently every iteration
  in the evidence run cleared it; the bar isn't the problem.

---

## Proposals

### 1. Target-dimension coverage replaces "all-dimensions" coverage

**Problem.** `heuristic_score()` awards `_DIMENSION_POINTS = 40` based
on how many of the configured dimensions appear in the findings text.
For a focused iteration on dimension X, this punishes the focus the
framework asked for: a 28KB broad survey hits all 8 dimensions and
maxes the points; a 9KB focused dive on dimension X mentions only
dimension X and scores 5/40.

**Evidence.** Iter 1 (broad, 28KB) coverage 85.0; iter 5 (focused on
Community, 6.9KB) coverage 50.0. The 35-point gap is mostly the
dimension-mentions component punishing focus.

**Fix.** `heuristic_score()` already accepts `explored_dimensions` as
an "unused, reserved for future" parameter. Add a `target_dimension:
str` parameter alongside it. Replace the dimension-mentions computation
with a depth-on-target metric:

- 70% of `_DIMENSION_POINTS` for keyword density of the *target*
  dimension's name and substring tokens within the findings.
- 30% retained for "no off-topic drift" — penalize findings that talk
  extensively about other dimensions (small subtraction, capped).

Caller in `src/research_loop.py` already knows the target dimension
(it generated the hypothesis). Pass it through.

**Code locations.** `src/scorer.py:heuristic_score()`,
`src/research_loop.py` (call site).

**Effort.** Small (~30 lines, no schema changes).

**Risk.** Low. Existing tests assert `heuristic_score()` returns 0.0
for empty findings — those still pass. New tests cover focused vs
broad findings against a known target.

**Acceptance.**
- Test fixture: a focused-on-target finding scores higher than a
  broad-but-shallow finding for that target.
- Re-running the evidence corpus through the new scorer produces iter
  2-6 totals in the 70-85 range while iter 1's broad pass drops to
  ~70 (still passes the gate, but no longer dominates).
- Existing `tests/test_scorer.py` continues to pass.

---

### 2. Novelty score against the current knowledge base

**Problem.** A finding that re-states what's already in
`knowledge_base.md` scores identically to one that introduces genuinely
new evidence. As iterations progress, the model can score well by
re-paraphrasing the corpus — the framework can't tell.

**Evidence.** The judge's `JUDGE_SCHEMA` already requires a `novelty:
1-10` field. The code averages it into `quality` and discards the
breakdown. Independent novelty is not measured at all.

**Fix.** Two layers, ship both:

1. **Cheap heuristic novelty.** Add `novelty_score(findings,
   knowledge_base) -> float` in `src/scorer.py`. Compute n-gram (n=4)
   overlap; novelty = `100.0 * (1 - overlap_ratio)`. Costs nothing,
   runs in milliseconds.
2. **Surface the judge's novelty separately.** Stop discarding the
   judge's `novelty` field. Carry it through `IterationScore` as a new
   `judge_novelty` field. No extra LLM cost.

Combine into total:

```
quality_blend = 0.7 * judge_quality + 0.3 * judge_novelty
total = 0.25 * coverage + 0.5 * quality_blend + 0.25 * heuristic_novelty
```

Tunable via config (`scoring.weights`). Default keeps roughly the
current behavior on iter-1-shaped findings while penalising restated
content on iter-N-shaped findings.

**Code locations.** `src/scorer.py` (new function + IterationScore
fields), `src/research_loop.py` (pass `knowledge_base` content into
the scorer), `src/config.py` (new `scoring.weights` block, optional
with current defaults if absent).

**Effort.** Medium. New function + dataclass fields + config schema +
threading through the call sites. ~150 lines + tests.

**Risk.** Medium. The composite formula change affects every score.
Mitigate by keeping the weights configurable and documenting the
default rationale. Snapshot the evidence run, replay through the new
scorer, compare distributions.

**Acceptance.**
- A finding identical to a snippet of the existing knowledge_base
  scores `heuristic_novelty < 20`. A finding with no overlap scores
  `heuristic_novelty > 80`.
- Replay of the evidence run shows iter 6 (similar topic to iter 1)
  scoring lower in novelty than iter 2 (different topic) — the metric
  detects topical proximity.
- Operators can disable the new components via config to recover the
  pre-change formula.

---

### 3. Surface score components in logs and dashboard

**Problem.** Operators see `coverage: 60.5, quality: 67.5, total:
64.7` and can't tell whether coverage was 60 because findings were
short, evidence types were missing, or content drifted off-topic.
Debugging requires reading source. Across a multi-iteration run with
diverging scores, this opacity compounds.

**Evidence.** `IterationScore` already carries `dimensions_covered`,
`gaps`, and `judge_raw` — they're written to artifacts but never
surfaced in the run.log. The judge's per-axis scores
(depth/accuracy/novelty/actionability) live in `judge_raw` and are
similarly hidden.

**Fix.** Three concrete changes:

1. Extend `IterationScore` with explicit component fields:
   `dimension_points: float`, `evidence_points: float`,
   `new_questions_points: float`, `length_points: float`,
   `judge_depth: int`, `judge_accuracy: int`, `judge_novelty: int`,
   `judge_actionability: int`. All additive — no breaking changes.
2. Update the log line in `src/research_loop.py`:
   ```
   Scores - coverage: 60.5 [target=18/28 evidence=14/15 questions=8/10
   length=20/30] quality: 67.5 [d=8 a=7 n=5 act=7] total: 64.7
   (judge: gemini-2.5-flash, dim best: 0.0, global best: 79.0)
   ```
3. Mirror in `dashboard.json`. Add a `score_breakdown` section per
   iteration with all components.

**Code locations.** `src/scorer.py` (IterationScore dataclass),
`src/research_loop.py` (log format), `src/artifacts.py` (dashboard
schema).

**Effort.** Small. ~50 lines, schema-additive only.

**Risk.** Very low. Existing artifact consumers see additional fields,
not changed ones.

**Acceptance.**
- Log line shows all 8 components plus the judge model name.
- `dashboard.json` includes `score_breakdown` for every iteration.
- Existing tests still pass; one new test verifies the breakdown is
  populated.
- Operators can answer "why was iter N's score low?" from `run.log`
  alone.

---

### 4. Optional multi-judge consensus

**Problem.** The single LLM judge concentrates style bias into a
single number. In the evidence run, Gemini judged quality 60-75; a
Codex or Claude judge would likely have produced different numbers on
the same findings.

**Evidence.** Gemini code-switched to Spanish in iterations 3-4 and
emitted dozens of meta-critique "new dimensions" that read as
hyper-strict criticism. A different judge would not have produced the
same `gaps` set, almost certainly not the same `quality` scores.

**Fix.** Allow multiple judge backends, weighted:

```yaml
evaluation:
  judges:
    - adapter: gemini-cli
      model: gemini-2.5-flash
      weight: 0.5
    - adapter: codex-cli
      model: gpt-5.4
      weight: 0.5
```

When `judges:` is set with 2+ entries, run them in parallel, average
the per-axis scores weighted by the configured weights, store
per-judge breakdowns in `IterationScore.judges: dict[str, JudgeResult]`.
Single-judge configs (the default) stay backward-compatible.

When two judges disagree by more than a threshold (configurable, e.g.
2 points on the 1-10 scale), emit a warning to the run.log and an
`audit_trail.jsonl` event. That signal is gold for operators
calibrating their setup.

**Code locations.** `src/scorer.py` (`call_judge()` becomes
`call_judges()`), `src/config.py` (new `evaluation.judges` schema),
`src/research_loop.py` (parallel calls via `asyncio.gather` or
threadpool — backends are subprocess-bound so simple parallelism is
fine).

**Effort.** Medium-large. New config schema, parallel execution,
result aggregation, disagreement detection, dashboard display.
~200 lines + tests + docs.

**Risk.** Medium. Doubles judge cost when enabled. Operators must
opt in. Existing single-judge runs unaffected.

**Acceptance.**
- A 2-judge config produces averaged scores, both judges' breakdowns
  in `dashboard.json`, and a warning event when they disagree by >2.
- Single-judge configs run identically to today (regression test).
- A real run with `claude-cli` + `gemini-cli` as judges produces
  observably different per-judge scores on identical findings.

---

### 5. Per-dimension expected evidence types

**Problem.** The current config has one global `evidence_types` list.
But "Licensing" needs `pricing_data`, "Migration" needs `code_example`,
"Community activity" needs commit-frequency / contributor-count data
that *aren't in the default catalog at all*. The 35-point evidence
component is therefore unscaled noise across dimensions.

**Evidence.** Iter 5 (Community / maintenance) coverage 50.0. The
default evidence types (`comparison_table, pricing_data, code_example,
trade_off_analysis`) are mostly inapplicable to that dimension —
the model lost evidence points it had no realistic way to earn.

**Fix.** Move evidence types from `scoring.evidence_types` to per-
dimension configuration. The existing `dimensions:` list is just
strings; promote each entry to a small object:

```yaml
dimensions:
  - name: "Migration effort from LocalStack..."
    expected_evidence: [code_example, comparison_table, trade_off_analysis]
  - name: "Community activity..."
    expected_evidence: [release_cadence, contributor_count]
  - name: "Licensing and pricing..."
    expected_evidence: [pricing_data, comparison_table]
```

Backward-compatible: a dimension that's still a bare string falls
back to the global default. New built-in evidence types
(`release_cadence`, `contributor_count`, etc.) ship with default
regex patterns; operators can extend via
`scoring.custom_evidence_patterns`.

`heuristic_score()` then scores evidence relative to the iteration's
*target* dimension's expected list, not the global catalog.

**Code locations.** `src/config.py` (DimensionConfig dataclass +
parse logic + backward-compat fall-through), `src/scorer.py`
(per-target evidence scoring, expanded `_EVIDENCE_PATTERNS`),
`configs/research/_template.yaml` (documentation), config templates
across the showcase.

**Effort.** Medium. Schema change, parser updates, scorer updates,
template updates. ~100 lines.

**Risk.** Medium. Schema migration for existing configs. Mitigated by
backward-compat: bare-string dimensions still work.

**Acceptance.**
- A config with mixed bare-string and object-form dimensions parses
  cleanly and runs.
- Iter 5-shape findings (Community dimension) score evidence points
  against `release_cadence` / `contributor_count` patterns rather
  than `pricing_data` / `code_example`.
- All existing showcase configs continue to run unchanged.

---

### 6. Diminishing-returns curve on word count

**Problem.** Substantive word count rewards length linearly up to
`_LENGTH_POINTS = 10` at `_TARGET_WORD_COUNT = 500.0`. Findings shorter
than 500 words get partial credit; findings longer hit the cap and
get no further reward. But within 0-500 words, every word counts
equally. The model has no signal that *concise dense findings* beat
*verbose padded findings*.

**Evidence.** Iter 1 (28KB) and iter 6 (11KB) both score the full
length cap. The 17KB difference between them gets no signal. Iter 5
(6.9KB) is below the cap and the model is incentivised to pad, not
to be selective.

**Fix.** Replace linear with logarithmic curve:

```python
length_points = min(_LENGTH_POINTS, log(words + 1) * 1.7)
```

This gives:
- 100 words → ~7.8 points
- 500 words → ~10 points (near cap)
- 5000 words → still ~10 points (no padding bonus)

Tune the `1.7` multiplier so 500 words still hits the existing target
score, preserving the heuristic's calibration on iter-1-shaped
findings.

**Code locations.** `src/scorer.py` (length component computation).

**Effort.** Tiny. ~5 lines.

**Risk.** Low. Calibrated to preserve current scoring at the
`_TARGET_WORD_COUNT = 500` mark.

**Acceptance.**
- 500-word fixture scores ~10 length points (matches today).
- 100-word fixture scores ~7.8 (was ~2.0).
- 10000-word fixture scores ~10 (was 10 — unchanged).
- Test: padding-style findings (lots of words, no new content) no
  longer score higher than concise findings on the length axis.

---

### 7. Cost-adjusted scoring metric (dashboard-only)

**Problem.** Two backends with different per-call costs producing
similar quality scores look identical in the dashboard. Operators
can't see that backend A reached score 75 for $0.10 while backend B
reached 78 for $1.00.

**Evidence.** The `dashboard.json` schema has no cost-efficiency view.
Each call's `cost_usd` is recorded but not normalised against quality.

**Fix.** Add `score_per_dollar: float` to per-iteration dashboard
records:

```python
score_per_dollar = total / max(cost_usd, 0.001)  # avoid div-by-zero
```

And a portfolio aggregation: `cost_efficiency_by_backend: dict[str,
float]` showing each backend's average score-per-dollar across all
runs. Visible in HTML/PDF reports.

Does *not* change the KEEP gate or the iteration-level score.
Purely informational, surfaced in reports.

**Code locations.** `src/artifacts.py` (dashboard payload),
`src/portfolio.py` (cross-run aggregation), HTML templates.

**Effort.** Small. ~30 lines, schema-additive.

**Risk.** Very low. No behavioral change; just new fields.

**Acceptance.**
- `dashboard.json` includes `score_per_dollar` per iteration.
- Portfolio view shows `cost_efficiency_by_backend` ranking.
- HTML report renders the new fields.

---

### 8. Cross-iteration depth bonus

**Problem.** `kept = score.total > prev_best AND score.total >= 30.0`
uses a per-dimension `prev_best`. Once a dimension hits 79.0 broadly,
a later focused refinement on the same dimension must beat 79.0 to be
kept — with the same breadth-biased scorer. The framework
*structurally cannot* refine a dimension once it's been broadly
covered.

**Evidence.** Iter 1's "Migration effort" hit 79.0 with a broad
survey. A hypothetical iter 7 with a deeper focused dive on the
*same* dimension would be discarded if it scored 75.0 — even though
it's higher quality per-token, with new evidence, on a topic the
operator wants more depth on.

**Fix.** Introduce a depth-multiplier for re-attempts:

```python
attempt = state.dimension_attempts.get(dimension, 0)
depth_multiplier = 1.0 + (0.15 * min(attempt, 3))  # 1.0, 1.15, 1.3, 1.45, capped
adjusted_score = score.total * depth_multiplier
kept = adjusted_score > prev_best AND score.total >= 30.0
```

Re-attempts on the same dimension get up to 1.45× weighting in the
KEEP comparison (capped at 4 attempts). Raw `score.total` is still
required to clear the absolute 30.0 floor, so we don't keep garbage
just because it's a re-attempt.

Show both raw and adjusted scores in the log:

```
Scores - ... total: 75.0 (adjusted: 86.3 with attempt-3 multiplier 1.15)
```

**Code locations.** `src/research_loop.py` (KEEP gate),
`src/run_state.py` (`dimension_attempts` already tracked), log format.

**Effort.** Small. ~20 lines + log format change.

**Risk.** Medium. Changes the KEEP semantic. First-attempt scoring is
unchanged (multiplier = 1.0). Operators who don't want this can disable
via config (`scoring.depth_bonus: 0.0` to fall back to current
behavior).

**Acceptance.**
- First attempt at a dimension scores identically to today.
- Second attempt at the same dimension can clear the gate at 86%
  of the prior best score (1/1.15) — encouraging refinement.
- A re-attempt scoring below 30.0 is still discarded (floor enforced
  on raw score).
- Test: a fixture that re-attempts the same dimension with a focused
  refinement is now KEPT where it was previously DISCARDED.

---

## Implementation order

Sequenced by impact-per-effort and dependency order. Each phase ships
independently and doesn't block the next.

### Phase 1 — observability + the breadth-bias fix (do these first)

| # | Item | Effort | Schema change |
|---|---|---|---|
| 3 | Surface score components in logs + dashboard | S | additive only |
| 1 | Target-dimension coverage replaces all-dims coverage | S | none |
| 6 | Diminishing-returns curve on word count | XS | none |

Rationale: (3) lands first because every later change is easier to
validate when components are visible in `run.log`. (1) is the highest-
impact behavioral fix and only ~30 lines. (6) is a 5-line cleanup
that's free to bundle here.

After Phase 1: re-run the evidence corpus and confirm iter 2-6 scores
no longer collapse vs iter 1. Snapshot the new distribution as the
baseline for Phase 2.

### Phase 2 — novelty signal (the hardest behavioral change)

| # | Item | Effort | Schema change |
|---|---|---|---|
| 2 | Heuristic novelty + surface judge novelty + composite formula | M | new config block, additive |

Rationale: novelty is the deepest change because it alters what the
framework optimizes for. Land it on top of Phase 1 so the components
are visible while you tune weights.

### Phase 3 — operator controls

| # | Item | Effort | Schema change |
|---|---|---|---|
| 5 | Per-dimension expected evidence types | M | dimension schema upgrade with backward-compat |
| 8 | Cross-iteration depth bonus | S | optional config flag |

Rationale: both are operator-controllable (per-dimension evidence is
opt-in via the new dimension object form; depth bonus has a config
multiplier). Ship together because they share documentation surface.

### Phase 4 — judge ensemble + cost views

| # | Item | Effort | Schema change |
|---|---|---|---|
| 4 | Multi-judge consensus | M-L | new evaluation.judges block |
| 7 | Cost-adjusted scoring metric in dashboard | S | additive only |

Rationale: most expensive features last. (4) doubles judge cost, so
operators only opt in once the cheaper improvements are exhausted.
(7) is small but conceptually pairs with (4) — once you have
multi-judge data, cost-per-quality becomes a meaningful comparison.

---

## Open questions

1. **Default weights for the composite formula in Phase 2.** Proposed
   `0.25 / 0.5 / 0.25` for `coverage / quality_blend / heuristic_novelty`.
   Should be calibrated against the evidence run to keep iter 1 in the
   same total ballpark.
2. **Threshold for multi-judge disagreement warnings.** Proposed 2
   points on the 1-10 axis. Tunable; default chosen to surface real
   divergences without spamming on routine variance.
3. **Per-dimension evidence-type catalog.** Proposed additions:
   `release_cadence`, `contributor_count`, `security_advisory`,
   `migration_runbook`. Need to define regex patterns matching real-
   world findings shapes.
4. **Should the depth bonus apply to the absolute 30.0 floor?**
   Proposed: no — raw `score.total >= 30.0` always required, only the
   `> prev_best` comparison gets the multiplier. Keeps the floor
   honest.

## Future considerations (deferred from scope)

- **Calibration against the benchmark catalog.** `benchmark_catalog/`
  has 5 lightweight benchmarks today. If they were promoted to gold-
  answer datasets, scoring could include "did findings cover the
  expected_dimensions and required_keywords?" as a separate axis.
  Needs a benchmark catalog plan first.
- **Adversarial baseline scoring.** Run the same hypothesis prompt
  with no tools allowed; score the actual research relative to that
  baseline. Captures whether the research loop added value beyond the
  model's prior knowledge. Expensive (extra LLM call per iteration).
- **Self-critique pass.** Have the same model that produced the
  findings critique its own work before the judge sees it. Cheap form
  of internal review. Doesn't replace the adversarial judge but adds
  another signal.

## Acceptance for the plan as a whole

The plan is complete when:

- All 8 proposals are implementable as described, with the specified
  code locations actually existing in the repo today.
- Each phase can ship independently without breaking the others.
- Operators can opt out of every behavioral change via config and
  recover the pre-change scoring formula.
- Re-running the evidence corpus
  (`output/localstack_alternatives_copilot_gemini`) through the fully-
  implemented pipeline produces a more even score distribution across
  iterations, with novelty visibly tracking corpus growth.
