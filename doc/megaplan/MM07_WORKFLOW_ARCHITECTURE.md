# Agent Task: Mega Milestone 7 — Workflow State Machine, Phase Contracts, Shared Decisions

## Goal
Import the strongest AutoResearchClaw ideas: explicit workflow states, phase contracts, and shared decision semantics.

## Constraints
- TDD only
- Never build
- Commit each step separately
- Stop after each step for review
- Preserve existing `run`, `refine`, `plan` behavior unless contract explicitly changes it

## Non-goals
- Full orchestrator rewrite
- Collapsing all modes into one loop
- New runtime sandbox work

## Step 1 — Workflow state modules
Add:
- `src/workflows/research_states.py`
- `src/workflows/refine_states.py`
- `src/workflows/plan_states.py`

### Deliverables
- state enums
- terminal/pause/resume states
- transition maps

### Commit
`feat: add workflow state models`

---

## Step 2 — Phase enums and transition emission
Define explicit phase enums per mode and emit workflow transition events into audit trail.

### Deliverables
- research/refine/plan phase enums
- audit events for state transitions

### Commit
`feat: emit workflow state transitions`

---

## Step 3 — Contract data model
Add machine-readable phase contracts.

### Deliverables
- `src/workflows/contracts.py`
- research/refine/plan contract modules
- inputs, outputs, done criteria, retry policy, human gate flags

### Commit
`feat: add workflow phase contracts`

---

## Step 4 — Shared decision model
Normalize decision vocabulary across modes.

### Deliverables
- `src/workflows/decisions.py`
- mappings from keep/discard, valid/stale/deferred, etc.

### Commit
`feat: unify workflow decision states`

---

## Step 5 — Diagnostics integration
Teach `doctor` and `explain` to report current phase, missing contract requirements, resumability, and pending human gates.

### Commit
`feat: surface workflow contracts in diagnostics`

## Acceptance criteria
- workflow semantics are centralized
- phase correctness is diagnosable
- shared decision vocabulary exists across modes
