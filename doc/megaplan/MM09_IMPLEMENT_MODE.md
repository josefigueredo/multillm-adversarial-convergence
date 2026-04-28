# Agent Task: Mega Milestone 9 — Safe Adversarial Implement Mode

## Goal
Add a first-class `implement` mode for adversarial code work with explicit target-repo safety boundaries.

## Constraints
- TDD only
- Never build
- Commit per step
- Stop for review after each step
- Patch-only must be the default

## Non-goals
- Self-editing this planner repo by default
- Forcing code automation into `run`
- Direct in-place apply as default

## Step 1 — Implement mode scaffolding
Add:
- `src/implement_loop.py`
- `src/implement_strategy.py`
- `src/implement_runner.py`
- CLI entrypoint

### Commit
`feat: scaffold implement mode`

---

## Step 2 — Target repo contract
Require explicit target path, allowed roots, and execution level.

### Execution levels
- `analyze_only`
- `patch_only`
- `isolated_apply`

### Commit
`feat: add implement target repo contract`

---

## Step 3 — Adversarial implementation workflow
Builder/challenger/verifier/arbitrator loop for code tasks.

### Deliverables
- patch generation
- critique bundle
- accepted critique integration

### Commit
`feat: add adversarial implement workflow`

---

## Step 4 — Safety guardrails
Prevent unsafe self-hosting defaults; require high-friction opt-in for same-repo targets.

### Commit
`feat: enforce implement self-hosting safety`

---

## Step 5 — Artifacts and diagnostics
Persist patches, critiques, accepted changes, rollback notes, and doctor/explain coverage.

### Commit
`feat: add implement artifacts and diagnostics`

## Acceptance criteria
- `implement` is separate from `run`
- target repo separation is explicit
- patch-only is default
- self-hosting is constrained by architecture
