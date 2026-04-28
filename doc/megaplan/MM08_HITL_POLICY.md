# Agent Task: Mega Milestone 8 — Policy-Driven HITL and Workflow Gating

## Goal
Turn HITL from a verifier-only escape hatch into a configurable workflow policy layer.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop for review after each step

## Non-goals
- Replacing existing HITL mechanisms
- New product modes
- Broad UX redesign

## Step 1 — Intervention mode config
Add config-level intervention modes:
- `full_auto`
- `checkpoint_only`
- `decision_only`
- `co_pilot`
- `step_review`

### Commit
`feat: add workflow intervention modes`

---

## Step 2 — Workflow gates
Attach configurable human gates to meaningful workflow transitions.

### Deliverables
- gate definitions per mode
- pause-before / pause-after semantics

### Commit
`feat: add workflow hitl gates`

---

## Step 3 — Guidance injection
Persist structured human guidance and inject it into the next phase.

### Commit
`feat: add structured hitl guidance injection`

---

## Step 4 — Review packets
Emit structured non-interactive review packets summarizing state, open issues, and candidate decisions.

### Commit
`feat: add workflow review packets`

---

## Step 5 — Diagnostics/docs
Update doctor/explain/docs to show intervention mode, pending gates, and guidance expectations.

### Commit
`docs: align hitl policy diagnostics`

## Acceptance criteria
- HITL is configurable at workflow level
- human gates are explicit and diagnosable
- guidance survives pause/resume cleanly
