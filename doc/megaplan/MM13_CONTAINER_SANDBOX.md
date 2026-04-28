# Agent Task: Mega Milestone 13 — Container-Backed Sandbox Backend

## Goal
Add an optional container-backed sandbox backend behind the existing sandbox executor contract.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop after each step
- Must remain optional

## Non-goals
- Container-first rewrite
- Breaking local-process sandbox path
- Pretending support is universal across platforms

## Step 1 — Container backend interface
Add `src/sandbox/backends/container.py` behind the same base interface introduced earlier.

### Commit
`feat: add container sandbox backend scaffold`

---

## Step 2 — Config and backend selection
Add config selection for local vs container sandbox backend.

### Commit
`feat: add sandbox backend selection`

---

## Step 3 — Workspace/env/write behavior mapping
Map existing workspace/env/write semantics onto container execution.

### Commit
`feat: map sandbox policy into container backend`

---

## Step 4 — Diagnostics and truthfulness
Update doctor/explain/docs to state platform limits, backend type, and actual guarantees.

### Commit
`docs: align container sandbox diagnostics`

---

## Step 5 — Safety and fallback behavior
Ensure clear fallback/error behavior when container runtime is unavailable.

### Commit
`feat: add container sandbox fallback behavior`

## Acceptance criteria
- container backend is optional and swappable
- local backend remains intact
- diagnostics are honest about guarantees and platform constraints
