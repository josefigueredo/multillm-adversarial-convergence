# Discovery Quality Plan

Concrete plan to fix the noise problem in the research-mode "new
dimension discovered" channel and to turn discovery into a useful
signal-extraction surface. Sibling to `docs/plans/scoring-enhancements.md`;
cross-references called out where the two plans depend on each other.

## Context

The framework's "new dimension discovered" log lines come from the
LLM judge's `gaps_identified` field in `JUDGE_SCHEMA` (defined in
`src/scorer.py`):

```python
"gaps_identified": {
    "type": "array",
    "items": {"type": "string"},
}
```

The judge emits an array of free-form strings; the framework records
them verbatim in `state.discovered_dimensions` (`src/run_state.py`)
and persists them to `results.tsv` (`discovered_gaps` column). On
subsequent iterations, the hypothesis-generator's
`{unexplored_dimensions}` placeholder receives the union of:

- Originally configured dimensions not yet explored
- Newly discovered dimensions from prior iterations

There is **zero filtering** between the judge's output and the
discovered-dimensions pool. That "trust the judge unconditionally"
invariant is the root of the noise problem.

### What the run revealed

The 6-iteration `localstack_alternatives_copilot_gemini` run produced
this discovery profile:

| Iter | Dimension | New dims emitted | Substantive | Critique-shaped | Off-topic / noise |
|---|---|---|---|---|---|
| 1 | Migration effort | 8 | 6 | 1 | 1 |
| 2 | CI/CD integration | 8 | 5 | 2 | 1 |
| 3 | Terraform/CDK/SAM | **22** | 4 | 16 | 2 (Spanish meta-critiques) |
| 4 | AWS service coverage | 7 | 5 | 2 | 0 |
| 5 | Community / maintenance | 4 | 3 | 1 | 0 |
| 6 | Licensing / pricing | **17** | 8 | 7 | 2 |

Three structural problems surface:

1. **Most "discoveries" are not investigatable research targets.**
   Iter 3's 22-entry dump included items like *"Subjective claim of
   `superior` endpoint lacks evidence"* and *"Subjectivity of `major`
   alternatives and `within weeks`"*. These are critiques of the
   existing findings, not new dimensions to investigate. The hypothesis-
   generator can't act on them.
2. **Single-judge discovery has single-judge bias.** Gemini emitted
   critique-shaped gaps and code-switched to Spanish in iter 3-4. A
   different judge would have produced a different (likely better-
   shaped) set. There is no signal to detect this — the framework
   accepts whatever the judge produces.
3. **There is no signal that a gap is real vs hallucinated.** A gap
   mentioned by one iteration is treated identically to a gap that
   would emerge across multiple iterations and judges. Iteration
   redundancy carries information that the framework currently throws
   away.

Plus a secondary architectural issue:

4. **Critique-shaped gaps point at depth, not breadth.** When the
   judge says *"subjective claim about X lacks evidence"*, the correct
   response is to *re-investigate dimension X with stricter sourcing*,
   not to add "the subjectivity of X" as a new dimension. The
   framework currently has no path to do that — see scoring plan
   Proposal 8 (cross-iteration depth bonus). Discovery and depth
   need each other.

## Goals

- Constrain what the judge emits as a "gap" so its shape matches
  what the hypothesis-generator can act on.
- Filter obvious noise (duplicates, language drift, critique
  templates) before gaps enter the framework's state.
- Use cross-iteration redundancy as a quality signal — gaps that
  re-emerge are higher-confidence than one-offs.
- Allow operators to inspect why a gap was promoted, demoted, or
  filtered without reading source.
- Route critique-shaped gaps to depth-refinement of the original
  dimension instead of the new-dimension pool.

## Non-goals

- Eliminating critique-shaped output entirely. Critiques are useful
  signal — they should be captured and surfaced, just not treated as
  new dimensions to investigate.
- Rewriting the hypothesis-generator. Its `{unexplored_dimensions}`
  contract stays — only the contents of that pool change.
- Changing single-judge runs into multi-judge runs by default.
  Multi-judge is a scoring-plan opt-in; this plan integrates with it
  but does not require it.
- Touching `JUDGE_SCHEMA` for fields outside `gaps_identified`. The
  rest of the schema (depth/accuracy/novelty/actionability/dimensions
  _covered/reasoning) is owned by the scoring plan.

---

## Proposals

### 1. Constrain gap shape at the source (prompt + JSON schema)

**Problem.** `JUDGE_SCHEMA["gaps_identified"]` accepts any array of
strings. The judge fills it with whatever feels relevant — including
critiques, restatements, language-drift items, and one-word fragments.
The schema places no constraint on shape, length, or category.

**Evidence.** Iter 3's 22 emitted gaps included items like
*"Subjectivity of 'Major' Alternatives and 'Within Weeks'"* (12 words,
critique-shaped, references existing findings) and
*"Verificación de números de tipos de recursos en CloudFormation"*
(Spanish, references iter-2 content, not actionable). Both passed the
schema as-is and entered the discovered pool.

**Fix.** Two changes, one upstream:

1. **Upgrade `gaps_identified` to a structured object.** New shape:

   ```python
   "gaps_identified": {
       "type": "array",
       "items": {
           "type": "object",
           "properties": {
               "topic": {"type": "string", "minLength": 20, "maxLength": 200},
               "why_it_matters": {"type": "string", "minLength": 30, "maxLength": 500},
               "kind": {
                   "type": "string",
                   "enum": ["research_target", "critique", "refinement"],
               },
               "investigatable": {"type": "boolean"},
               "confidence": {"type": "integer", "minimum": 1, "maximum": 10},
           },
           "required": ["topic", "why_it_matters", "kind", "investigatable", "confidence"],
       },
   }
   ```

2. **Update the judge prompt** (`prompts/research_semantic_judge.md`,
   adjacent to wherever `JUDGE_SCHEMA` is consumed) with a clear
   gap definition:

   > A gap is a SPECIFIC technical question or evidence type missing
   > from the findings that would meaningfully improve a decision-
   > maker's confidence. A gap is investigatable — someone could go
   > research it. Mark `kind: research_target` for new dimensions to
   > investigate, `kind: refinement` for "re-investigate this existing
   > dimension with better evidence", `kind: critique` for stylistic
   > or methodological concerns about the current findings. Set
   > `investigatable: false` for critiques. Confidence reflects how
   > sure you are this gap is real (1 = speculative, 10 = certain).

**Code locations.** `src/scorer.py` (`JUDGE_SCHEMA`),
`prompts/research_semantic_judge.md` (gap definition), the gap
consumer in `src/research_loop.py` (parse the new shape).

**Effort.** Small. Schema upgrade + prompt rewrite + parser update.
~80 lines + tests.

**Risk.** Medium. Schema change affects every judge call. Mitigate
with a transition window: parser accepts both the new object form
*and* the old bare-string form (treating bare strings as
`{topic: <string>, kind: "research_target", investigatable: true,
confidence: 5}`). Drop the bare-string compatibility once all judges
emit the new shape reliably.

**Acceptance.**
- Judge prompts produce >90% schema-compliant `gaps_identified`
  arrays across claude-cli, codex-cli, gemini-cli on a fixed set of
  10 hand-graded test prompts.
- A bare-string judge response (legacy shape) parses cleanly via the
  compatibility shim.
- Existing tests in `tests/test_scorer.py` continue to pass with the
  shim active.

---

### 2. Intake processing pipeline

**Problem.** Even with Proposal 1's schema in place, the judge will
still occasionally emit duplicates, language-drift items, or items
that pass the schema but fail common-sense filters. The framework
currently has no processing layer between the judge's response and
`state.discovered_dimensions`.

**Evidence.** Iter 3 and iter 4 both emitted *"MiniStack Init Hook
Volume Mount Path Uncertainty"* — duplicate work that occupied two
slots in the discovered pool. The Spanish entries in iter 3 would not
have been caught by Proposal 1's schema (they pass length and shape
constraints) but are obvious noise on a language filter.

**Fix.** Add `process_discovered_gaps(raw_gaps, state, config)` in
`src/research_loop.py` that runs each gap through:

1. **Normalize.** Trim whitespace, collapse internal whitespace, strip
   trailing punctuation. Compute a canonical form: lowercase, remove
   stop words, sort tokens alphabetically. Stored as `canonical_topic`
   for matching.
2. **Deduplicate against existing.** Skip if `canonical_topic` matches
   any entry in `config.dimensions ∪ state.discovered_gaps` within an
   edit-distance threshold (proposed: Levenshtein ratio < 0.85 = match).
3. **Language filter** (optional, controlled by
   `discovery.language_filter: en | none`). Run `langdetect` (already
   a small dep) on `topic`; reject non-`en` items if filter is `en`.
4. **Length filter.** Reject if `topic` < 30 chars or > 200 chars
   after normalization.
5. **LLM-validator** (optional, controlled by
   `discovery.llm_validation: true | false`, default `false`). When
   enabled, run a single small-model call:

   > "Of these gaps, classify each as `research_target`,
   > `refinement`, `critique`, or `noise`. Output JSON."

   Drop everything classified `noise`. Cheap with Haiku / Gemini Flash.

Each filtered gap is logged to `audit_trail.jsonl` with the rejection
reason (`duplicate`, `non_english`, `too_short`, `validator_noise`)
so operators can inspect what was thrown out.

**Code locations.** `src/research_loop.py` (new function + call site
between judge response and state mutation), `src/config.py` (new
`discovery` block, optional with sensible defaults),
`pyproject.toml` (add `langdetect` if filter is enabled by default),
`src/audit_trail.py` (new event types: `gap_filtered_*`).

**Effort.** Medium. ~120 lines core + tests. LLM validator adds
another ~50 lines if enabled.

**Risk.** Medium. Aggressive filtering could drop legitimate gaps
that happen to look like duplicates of configured dimensions. Mitigate
with the `audit_trail` event so operators can see what was filtered
and adjust thresholds. Default thresholds tuned conservatively.

**Acceptance.**
- A judge response with two near-identical gaps (one of which matches
  an existing dimension within edit-distance threshold) results in
  one stored entry, with both `gap_filtered_duplicate` events
  recorded.
- A Spanish-language gap is filtered when `language_filter: en`,
  passed when `language_filter: none`.
- A 12-character gap (`"missing X"`) is filtered for length.
- `audit_trail.jsonl` shows the rejection reason for every filtered
  gap.
- Existing single-judge runs see no behavioral change when the new
  config block is absent (defaults preserve current behavior).

---

### 3. Cross-iteration clustering with re-discovery promotion

**Problem.** Gaps emitted by one iteration are treated identically
to gaps that would re-emerge across many iterations and (with the
scoring-plan multi-judge work) across multiple judges. The framework
discards the convergence signal — repetition is the strongest
quality indicator we have, and we don't measure it.

**Evidence.** Looking at the run, the *substantive* gaps tended to
re-appear across iterations: "MiniStack Init Hook Volume Mount Path"
appeared in iter 3 and iter 4; "Floci's persistence bug fix status
in versions after v1.4.0" appeared in iter 1 and was implicit in
several later iterations. The *noise* gaps appeared once and never
again ("Subjectivity of 'major'", "imprecise age reporting"). This
asymmetry is exactly what convergence-based promotion would exploit.

**Fix.** Replace `state.discovered_dimensions: list[str]` with
`state.discovered_gaps: dict[str, GapEntry]`:

```python
@dataclass
class GapEntry:
    canonical_topic: str
    display_topic: str          # most recent display form
    first_seen_iter: int
    occurrences: int = 1
    iterations_seen: list[int] = field(default_factory=list)
    judges_seen: list[str] = field(default_factory=list)  # backend names
    kind: str = "research_target"
    confidences: list[int] = field(default_factory=list)
    promoted: bool = False
```

When a gap arrives (after Proposal 1 + 2 processing), match
`canonical_topic` against existing entries with the same edit-
distance threshold. If matched: increment `occurrences`, append
iteration + judge, update `display_topic` to the latest. If not:
create a new entry.

A gap is **promoted** (eligible for the hypothesis pool) when:

```python
promoted = (
    occurrences >= 2
    OR (occurrences == 1 AND len(judges_seen) >= 2)  # only with multi-judge
    OR (occurrences == 1 AND mean(confidences) >= 8)  # high confidence
)
```

The hypothesis-generator's `{unexplored_dimensions}` placeholder
receives:
- Originally configured dimensions not yet explored
- `state.discovered_gaps` entries where `promoted == True`

Un-promoted gaps stay in state, accumulate occurrences/confidences
across iterations, and become eligible when they hit the threshold.

**Cross-reference: scoring plan Proposal 4 (multi-judge consensus)**.
Single-judge runs see promotion only via `occurrences >= 2` or
high-confidence shortcut. Multi-judge runs unlock the
`occurrences == 1 AND judges_seen >= 2` path, which is the most
elegant promotion signal — different judges independently
identifying the same gap is overwhelming evidence it's real.

**Code locations.** `src/run_state.py` (state schema + serialization),
`src/research_loop.py` (gap intake + promotion check + hypothesis
prompt context), `src/artifacts.py` (results.tsv format upgrade —
JSON-encoded gaps column or sidecar `discovered_gaps.json`),
`src/audit_trail.py` (new event: `gap_promoted`).

**Effort.** Medium-large. State schema migration is the heavy part —
existing runs with `results.tsv` in the old format need to load
cleanly. ~250 lines + tests + migration.

**Risk.** Medium. Backward compatibility with existing `results.tsv`
format requires careful migration. Mitigate by accepting both old
(`discovered_gaps: comma-separated strings`) and new
(`discovered_gaps: JSON-encoded array of GapEntry`) forms during
load; always write the new form.

**Acceptance.**
- A gap that appears in iter 1 and iter 3 is stored once with
  `occurrences=2, iterations_seen=[1, 3], promoted=True`.
- A gap that appears once with `confidence=9` is `promoted=True`.
- A gap that appears once with `confidence=5` is `promoted=False`
  and stays out of the hypothesis pool.
- Multi-judge run: a gap emitted by judge A in iter 1 and by judge B
  in iter 1 (same iteration, two judges) is `promoted=True` via the
  `judges_seen >= 2` path.
- Resume from an old-format `results.tsv` migrates cleanly to the
  new schema.
- `audit_trail.jsonl` records every `gap_promoted` event with the
  triggering rule (`occurrences`, `judges`, or `confidence`).

---

### 4. Classify gaps and dispatch by kind

**Problem.** Even with Proposals 1-3 in place, the framework treats
all promoted gaps as candidate dimensions for the hypothesis-
generator. But Proposal 1 introduces a `kind` field with three
values: `research_target` (new dimension), `refinement` (re-
investigate existing), `critique` (commentary on current findings).
The framework should route them differently.

**Evidence.** Iter 3's 22-emit dump included multiple items like
*"MiniStack `CODE FREEZE DUE MIGRATION` - Source Ambiguity"* and
*"MiniStack Init Hook Volume Mount Path Uncertainty"*. These are
`refinement` requests on the iter-1 Migration findings — the right
response is to re-do iter 1's work with stricter sourcing, not to
add "Source Ambiguity" as a new dimension. Today the framework
cannot do that because of the per-dimension `score.total > prev_best`
gate (scoring plan Proposal 8).

**Fix.** Route gaps by `kind` to different parts of the pipeline:

- `kind: research_target` → enters the `discovered_gaps` pool, gets
  promotion-evaluated per Proposal 3, eligible to enter
  `{unexplored_dimensions}`.
- `kind: refinement` → enters a separate `state.refinement_requests:
  dict[str, list[RefinementRequest]]` keyed by the dimension being
  refined. The hypothesis-generator's prompt includes a separate
  `{refinement_candidates}` section listing dimensions where
  refinement is requested, with the specific issues. The strategist
  picks a dimension to re-investigate from this pool when scoring's
  depth-bonus is enabled.
- `kind: critique` → recorded in `state.critiques` and surfaced in
  the dashboard's `critiques_summary`, but does NOT enter the
  hypothesis pool. Operator-facing signal only.

**Cross-reference: scoring plan Proposal 8 (cross-iteration depth
bonus)**. Refinement-shaped gaps are only actionable when the depth
bonus is enabled — without it, re-attempting a previously-scored
dimension is structurally impossible to KEEP. This proposal
*requires* scoring Proposal 8; ship them as a coordinated pair.

**Code locations.** `src/run_state.py` (new `refinement_requests`
and `critiques` fields), `src/research_loop.py` (intake dispatcher
+ hypothesis prompt context + interaction with depth bonus),
`prompts/research_hypothesis.md` (new `{refinement_candidates}`
section in the prompt template), `src/artifacts.py` (dashboard
`critiques_summary` payload).

**Effort.** Large. State schema additions, hypothesis prompt
rewrite, dispatcher logic, dashboard surface. ~300 lines + tests +
prompt iteration. Adds dependency on scoring plan Proposal 8.

**Risk.** Medium-high. Hypothesis prompt rewrite is the hardest
part — the template must clearly distinguish "pick a new dimension"
from "pick a refinement target" and produce different output
shapes. Test against multiple judges to validate the model
correctly uses the additional context.

**Acceptance.**
- A gap with `kind: refinement` referencing dimension X enters
  `state.refinement_requests[X]`, not `discovered_gaps`.
- The hypothesis prompt includes a `{refinement_candidates}` section
  when refinement requests exist.
- A research run with `scoring.depth_bonus: 0.15` (scoring plan
  Proposal 8) and refinement requests on dimension X correctly
  produces a re-attempt iteration on X with the depth multiplier
  applied.
- `kind: critique` gaps appear in `dashboard.json.critiques_summary`
  but never in the hypothesis pool.
- A run with no `kind` field on incoming gaps (legacy shape)
  defaults all gaps to `research_target` — no behavioral change.

---

### 5. Tier gaps by judge confidence

**Problem.** Proposal 1's schema introduces a `confidence: 1-10`
field on each gap. Proposal 3 already uses it as one promotion
shortcut (high-confidence single-iteration gaps get promoted). A
related question: should the hypothesis-generator *prefer* high-
confidence gaps when picking from a non-empty pool?

**Evidence.** No direct evidence yet — judges weren't producing
confidence in the existing run. Proposal 1 adds the field; this
proposal exploits it once it's available.

**Fix.** When the hypothesis-generator's `{unexplored_dimensions}`
pool contains both originally-configured dimensions and promoted
gaps, sort the gaps by `mean(confidences)` descending. The prompt
template signals this ordering:

> Configured dimensions to consider:
> - <list>
>
> Discovered gaps (sorted by judge confidence, highest first):
> - <topic> (confidence: 8.5, seen 3× across iterations [1, 3, 5])
> - <topic> (confidence: 7.0, seen 2× across iterations [2, 4])

The strategist still picks freely — confidence is a hint, not a
gate. But the prompt structure nudges toward higher-confidence
picks.

**Cross-reference: this is small enough to fold into Proposal 3's
implementation.** I'm calling it out as a separate proposal because
the *prompt-structure* change has implications for hypothesis
prompt-engineering that are independent from the state-schema
changes in Proposal 3.

**Code locations.** `prompts/research_hypothesis.md` (new section
in the unexplored-dimensions context), `src/research_loop.py`
(sort + format the gaps section).

**Effort.** Tiny. ~20 lines, mostly prompt formatting.

**Risk.** Low. Worst case: the strategist ignores the sort and the
prompt is verbose but harmless. Mitigate by keeping the section
concise and only including it when promoted gaps exist.

**Acceptance.**
- Hypothesis prompt sorts promoted gaps by mean confidence
  descending.
- A test fixture with 3 promoted gaps at confidences 5, 8, 9
  produces a prompt with the gaps in 9 → 8 → 5 order.
- A run with no promoted gaps produces no `Discovered gaps`
  section in the hypothesis prompt (no empty header noise).
- Operator survey: across 5 real runs, the strategist picks the
  higher-confidence option more often than chance (qualitative
  validation, not a hard test).

---

### 6. Persistent gap state schema upgrade

**Problem.** Proposals 2-5 all assume a richer gap representation
than the current `state.discovered_dimensions: list[str]`. That
schema lives in three places: in-memory state, `results.tsv` (the
`discovered_gaps` column), and the `audit_trail.jsonl` event
payloads. All three need a coordinated upgrade.

**Evidence.** Today's persistence: `results.tsv` row has a
`discovered_gaps` column that's a comma-separated string. Loading
re-parses to a list of strings. No room for `kind`, `confidence`,
`occurrences`, or any of the per-gap metadata Proposals 1-5
introduce.

**Fix.** Three coordinated changes:

1. **In-memory state**: replace `discovered_dimensions: list[str]`
   with `discovered_gaps: dict[canonical_topic, GapEntry]` (per
   Proposal 3's schema), plus `refinement_requests` and `critiques`
   (per Proposal 4).
2. **`results.tsv`**: add a sidecar file `discovered_gaps.json`
   that holds the full structured state. The `results.tsv`
   `discovered_gaps` column becomes a fallback for old-format
   loaders (writes the canonical topics only).
3. **`audit_trail.jsonl`**: define new event types per the earlier
   proposals (`gap_filtered_duplicate`, `gap_filtered_non_english`,
   `gap_filtered_too_short`, `gap_filtered_validator_noise`,
   `gap_promoted`, `gap_classified`).

Backward compatibility: `--resume` loads `discovered_gaps.json`
when present, falls back to parsing the old `discovered_gaps`
column when not. Always writes both on save.

**Code locations.** `src/run_state.py` (state schema + load/save
both formats), `src/artifacts.py` (sidecar JSON writer),
`src/audit_trail.py` (new event types), tests for migration.

**Effort.** Medium. ~150 lines including the migration shim and
tests covering both legacy-load and new-load paths.

**Risk.** Low. Sidecar approach means existing `results.tsv`
consumers see no change. New consumers can read the JSON sidecar
directly. Migration is one-way (write new, read both).

**Acceptance.**
- A new run produces both `results.tsv` (old format) and
  `discovered_gaps.json` (new format).
- `--resume` from a fresh new-format run loads cleanly from
  `discovered_gaps.json`.
- `--resume` from an old-format-only run (no sidecar) loads via the
  legacy column-parser, treating each gap as
  `{topic: <string>, kind: research_target, confidence: 5,
  occurrences: 1, iterations_seen: [<best-effort>]}`.
- An audit run can replay all `gap_*` events from
  `audit_trail.jsonl` and reconstruct the discovered_gaps state.

---

## Implementation order

Sequenced by dependency and impact-per-effort. Phase 1 ships
independently; later phases assume the earlier phases.

### Phase 1 — source quality (do these first)

| # | Item | Effort | Schema change |
|---|---|---|---|
| 1 | Constrain gap shape at the source (prompt + schema) | S | additive with shim |
| 2 | Intake processing pipeline (normalize, dedupe, filter) | M | new `discovery` config block |

Rationale: (1) catches noise at the source; (2) catches what slips
through. The two together address the 80% case (duplicates, language
drift, length anomalies, critique-shaped strings) without requiring
any state-schema changes.

After Phase 1: re-run the evidence corpus (or a representative
shorter run) and confirm the 22-entry iter 3 dump drops to ~5-7
substantive gaps. Snapshot the cleanup rate as the baseline.

### Phase 2 — persistent state schema

| # | Item | Effort | Schema change |
|---|---|---|---|
| 6 | Persistent gap state schema upgrade | M | additive (sidecar JSON, legacy-compat) |

Rationale: foundation for Phases 3-4. Land on its own so the
schema migration is debugged independently of any behavioral
changes.

### Phase 3 — convergence as quality signal

| # | Item | Effort | Schema change |
|---|---|---|---|
| 3 | Cross-iteration clustering with re-discovery promotion | M-L | uses Phase 2 schema |
| 5 | Tier gaps by judge confidence | XS | prompt template only |

Rationale: (3) is the most transformative change in this plan —
turns the noise problem into a signal-extraction problem. (5) is
small enough to bundle here as a sub-task of (3); separated in this
plan for conceptual clarity.

(3) gets dramatically stronger when paired with **scoring plan
Proposal 4 (multi-judge consensus)**. Recommend coordinating: ship
Phase 3 here either after or alongside scoring plan Phase 4.

### Phase 4 — architectural separation of gap kinds

| # | Item | Effort | Schema change |
|---|---|---|---|
| 4 | Classify gaps and dispatch by kind | L | hypothesis prompt rewrite |

Rationale: most invasive change. Requires **scoring plan Proposal 8
(cross-iteration depth bonus)** as a hard prerequisite — without
the depth bonus, refinement-kind gaps have no path to acceptance.
Ship after scoring plan Phase 3 lands the depth bonus.

---

## Open questions

1. **Edit-distance threshold for canonical-topic matching.** Proposed
   Levenshtein ratio < 0.85. Too loose merges genuine new gaps with
   existing ones; too strict misses near-duplicates. Calibrate
   against the evidence run's gap corpus (manually grade pairs as
   "same gap" / "different gap" and tune until precision + recall
   balance).
2. **Should language filter be on by default?** Operator might run
   the framework in a non-English research context. Proposed
   default: `discovery.language_filter: en` for English-default
   prompts, but prompt templates should declare their expected
   language and the framework should default to that.
3. **Promotion threshold for `confidence`-only path.** Proposed
   `mean(confidences) >= 8` for single-occurrence promotion. Too low
   floods the hypothesis pool with noisy high-confidence claims;
   too high rejects valid one-shot insights. Calibrate against
   validation runs.
4. **What happens to un-promoted gaps after the run completes?**
   Proposed: persisted in `discovered_gaps.json` with
   `promoted: False` so future `--resume` calls can re-evaluate
   them as new evidence accumulates. They never expire automatically.
5. **Should `critique` gaps that re-emerge across iterations be
   promoted to `refinement`?** A critique that appears 3 times is
   strong signal that the original dimension needs re-investigation.
   Proposed: yes — auto-promote `critique` to `refinement` when
   `occurrences >= 3 AND len(judges_seen) >= 2`. Requires multi-judge.

## Future considerations (deferred from scope)

- **Embedding-based clustering instead of edit-distance.** A small
  embedding model (or reuse an aggregator API) could cluster
  semantically similar gaps that don't share surface tokens. More
  expensive than Levenshtein; better recall on rephrasings.
- **HITL operator approval for promoted gaps.** Before a discovered
  gap enters the hypothesis pool, optionally pause for operator
  approval (existing HITL infrastructure in `src/policy/`). Useful
  for high-stakes runs where operator wants final say on what
  counts as "new research scope".
- **Cross-run gap memory.** A user running multiple research topics
  might find the same gap appearing across runs. A repo-wide gap
  memory could surface "this gap appears in 4 of your last 10 runs
  on related topics" — strong meta-signal but adds significant
  storage and lifecycle complexity.
- **Auto-summarized critique digests.** When critiques accumulate,
  a periodic LLM call could produce a short "common critique themes
  across this run" summary in the dashboard. Useful for teams that
  want to harvest critique signal without acting on individual
  items.

## Acceptance for the plan as a whole

The plan is complete when:

- All 6 proposals are implementable as described, with the specified
  code locations actually existing in the repo today.
- Each phase ships independently and degrades gracefully when
  later-phase features are absent.
- Cross-references to scoring plan Proposals 4 and 8 are resolved
  (either both plans land their respective phases, or this plan's
  Phases 3-4 wait for them).
- Operators can opt out of every behavioral change via config and
  recover the pre-change discovery behavior (single-string gaps,
  no filtering, no clustering).
- Re-running the evidence corpus through the fully-implemented
  pipeline reduces iter 3's 22-gap dump to ≤8 substantive gaps,
  with the 14+ filtered items recorded in `audit_trail.jsonl` with
  rejection reasons.
- The promoted-gap pool (`promoted: True`) on the evidence corpus
  contains only gaps a human reviewer would agree are real research
  targets — qualitative acceptance, validated against a manual
  re-grading of the evidence run.
