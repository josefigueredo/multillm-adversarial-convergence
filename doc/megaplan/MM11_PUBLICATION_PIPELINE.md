# Agent Task: Mega Milestone 11 — Publication-Grade Deliverable Pipeline

## Goal
Separate synthesis from revision, packaging, and export so final outputs become publication-grade deliverables, not only reports.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop after each step

## Non-goals
- Replacing current reporting entirely
- Overleaf-specific integration first

## Step 1 — Deliverable pipeline model
Define stages like:
- synthesize
- revise
- package
- export

### Commit
`feat: add deliverable pipeline model`

---

## Step 2 — Deliverable classes
Make output pipelines explicit per class:
- paper
- technical doc
- executive brief
- decision memo

### Commit
`feat: add deliverable class pipelines`

---

## Step 3 — Citation/export verification
Add stronger coverage checks over deterministic references and publication packaging.

### Commit
`feat: add deliverable citation verification`

---

## Step 4 — Export bundles
Formalize export bundles with manifest, references, provenance, and revision notes.

### Commit
`feat: add deliverable export bundles`

---

## Step 5 — Diagnostics/docs
Teach doctor/explain/docs to distinguish synthesized vs packaged vs exported states.

### Commit
`docs: align publication pipeline states`

## Acceptance criteria
- final outputs have a staged publication pipeline
- report generation is no longer the only terminal concept
