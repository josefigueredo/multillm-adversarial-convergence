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
- the next highest-value rigor upgrade is conclusion-level certainty:
  - `certainty_tables.json`

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

## Recommended order

1. R1 — search and screening logs
2. R2 — methodology protocol expansion
3. R3 — reproducibility artifacts
4. R4 — certainty tables
5. R5 — external validation
