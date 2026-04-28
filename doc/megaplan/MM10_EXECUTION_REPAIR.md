# Agent Task: Mega Milestone 10 — Execution, Validation, Diagnosis, Repair

## Goal
Create a dedicated subsystem for execution attempts, validators, diagnosis artifacts, and repair loops.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop for review after each step

## Non-goals
- Replacing all critique loops
- Full CI orchestration platform

## Step 1 — Execution plan model
Add explicit execution-plan objects for commands/tools, expectations, and target context.

### Commit
`feat: add execution plan model`

---

## Step 2 — Validator layer
Separate validators from critics.

### Commit
`feat: add execution validator layer`

---

## Step 3 — Diagnosis artifacts
Emit diagnosis artifacts when execution/validation fails.

### Commit
`feat: add execution diagnosis artifacts`

---

## Step 4 — Repair loop
Add explicit repair cycles distinct from generic convergence.

### Commit
`feat: add execution repair loop`

---

## Step 5 — Integration
Integrate this subsystem into `implement` and selected evidence-generating research paths.

### Commit
`feat: integrate execution repair subsystem`

## Acceptance criteria
- execution attempts are explicit and inspectable
- validation is first-class
- failed execution yields diagnosis + repair path
