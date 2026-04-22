# Scientific Rigor Implementation Plan

This document turns `docs/design/scientific-rigor-roadmap.md` into an
implementation-oriented plan grounded in the current codebase.

## Status check

- inter-rater agreement is already implemented via `agreement.json`
- PRISMA-like logging is now implemented:
  - `search_log.json`
  - `screening_log.json`
- methodology protocol fields now include:
  - `review_type`
  - `search_sources`
  - `stopping_criteria`
  - `stopping_rationale`
  - `scoring_rationale`
- reproducibility artifacts are now implemented:
  - `prompt_snapshot.json`
  - `rerun.sh`
- conclusion-level certainty is now implemented:
  - `certainty_tables.json`
- the next highest-value follow-up is raw backend output policy:
  - decide whether capture is opt-in
  - define redaction and size limits
  - only then consider implementation

## Milestones

### R1 — PRISMA-like search and screening artifacts

Goal:
- persist what sources were considered
- persist which sources were included/excluded
- make screening decisions inspectable after the run

Scope:
- `search_log.json`
- `screening_log.json`
- dashboard/report summaries

### R2 — methodology protocol expansion

Goal:
- make `methodology:` closer to a pre-registered protocol

Candidate fields:
- `search_sources`
- `stopping_criteria`
- `stopping_rationale`
- `scoring_rationale`
- `review_type`

### R3 — reproducibility artifacts

Goal:
- snapshot prompts and rerun-critical metadata

Candidate artifacts:
- `prompt_snapshot.json`
- `rerun.sh`
- optional raw backend payload snapshots

### R4 — certainty tables

Goal:
- move from surface confidence labels to structured conclusion-level certainty

Candidate artifact:
- `certainty_tables.json`

### R5 — external validation track

Goal:
- human/gold-standard validation beyond internal rubricing

This is a research program, not a short implementation batch.

## Recommended next items

### Best next item — raw backend output capture policy

Goal:
- define the reproducibility boundary safely before storing raw backend payloads

Why:
- raw payloads can leak secrets
- payloads can become huge and noisy
- provider-specific junk is expensive to keep forever unless the storage contract is explicit

Recommendation:
- opt-in only
- final-response capture first
- redact secrets
- cap size aggressively

### Second best item — orchestrator cleanup

Goal:
- extract runtime telemetry and reproducibility helpers out of `src/orchestrator.py`

Why:
- the orchestrator is still coordinating too much artifact logic
- cleanup now is safer than cleanup after another large feature wave

Focus:
- telemetry accumulation
- reproducibility artifact writing
- report finalization helpers

### Third best item — richer certainty reporting

Goal:
- make certainty easier to interpret without reading raw JSON artifacts

Focus:
- factor-level certainty details in HTML/PDF
- portfolio certainty deltas across runs
- high-certainty recommendation counts
- tighter linkage between certainty and recommendation/factual claim classes

## Recommended order

1. R1 — search and screening logs
2. R2 — methodology protocol expansion
3. R3 — reproducibility artifacts
4. R4 — certainty tables
5. R5 — external validation
