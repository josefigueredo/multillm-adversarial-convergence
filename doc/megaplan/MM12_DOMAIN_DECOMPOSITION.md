# Agent Task: Mega Milestone 12 — Domain Decomposition into a Research Operating System

## Goal
Gradually reshape the repo so domain-bounded contexts become as explicit as runtime modules.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop for review after each step
- No big-bang refactor

## Non-goals
- Massive directory churn in one pass
- Rewriting stable runtime infrastructure

## Step 1 — Domain map
Create a domain map describing target bounded contexts and current file ownership.

### Commit
`docs: add research os domain map`

---

## Step 2 — Workflow/evidence/deliverables package seams
Introduce package boundaries for:
- workflows
- evidence
- deliverables

### Commit
`refactor: introduce domain package seams`

---

## Step 3 — Execution/implement bounded contexts
Carve out explicit modules for implementation automation and execution/repair.

### Commit
`refactor: separate execution and implement bounded contexts`

---

## Step 4 — HITL and policy boundaries
Make HITL policy modules independent of loop-specific code.

### Commit
`refactor: isolate hitl policy boundaries`

---

## Step 5 — Diagnostics/docs alignment
Update docs and diagnostics to reflect the domain architecture.

### Commit
`docs: align research os bounded contexts`

## Acceptance criteria
- domain contexts are clearer than before
- repo evolution becomes easier without god-object orchestration
