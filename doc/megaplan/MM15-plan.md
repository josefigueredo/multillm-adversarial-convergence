# MM15 Plan — Research OS File Migration

## Goal
Complete the domain decomposition started in MM12 by moving flat modules into their bounded-context packages.

## Important sequencing note
Do this **after MM16**, not before. Runtime semantics should be stabilized before structural migration churn.

## Critical rollout rule
Do **not** do big-bang move/update/delete steps.
Use this migration pattern:
1. move implementation into target package
2. keep thin compatibility shims at old flat paths
3. migrate callers gradually
4. remove shims only in the final cleanup step

## Rules
- TDD first
- Never build
- One commit per step
- Stop after each step for review
- No large delete-and-move batches
- Preserve backward compatibility until the final cleanup step

## Why this plan is 7 steps instead of 5
The original idea was too aggressive. `implement` and `policy` are too broad to migrate safely in one step, and deleting originals immediately is too risky.

---

## Step 1 — Move evidence internals behind package paths

### Change
Move evidence implementation modules into `src/evidence/`:
- references
n- provenance
- provenance_artifacts
- provenance_pipeline
- any closely coupled evidence helpers that clearly belong there

Keep flat compatibility shims at old module paths.

### Tests
- old flat imports still work
- new package module imports work
- `src.evidence` package exports still work

### Commit
`refactor: move evidence modules behind package seam`

---

## Step 2 — Move deliverables internals behind package paths

### Change
Move deliverable/publication modules into `src/deliverables/`:
- deliverable_pipeline
- deliverable_classes
- citation_verification
- export_bundle
- reporting / report_exports where appropriate

Keep flat compatibility shims.

### Tests
- old flat imports still work
- new package imports work
- package API unchanged

### Commit
`refactor: move deliverables modules behind package seam`

---

## Step 3 — Move execution internals behind package paths

### Change
Move execution/repair modules into `src/execution/`:
- execution_plan
- execution_validator
- execution_diagnosis
- execution_integration
- repair_loop

Keep flat compatibility shims.

### Tests
- old flat imports still work
- new package imports work
- execution package API unchanged

### Commit
`refactor: move execution modules behind package seam`

---

## Step 4 — Move implement-domain internals behind package paths

### Change
Move into `src/implement/`:
- implement_loop
- implement_runner
- implement_strategy
- plan_loop
- plan_refiner
- plan_strategy
- document_loop
- document_refiner
- document_strategy

Keep flat compatibility shims.

### Tests
- old flat imports still work
- new package imports work
- implement package API unchanged

### Commit
`refactor: move implement modules behind package seam`

---

## Step 5 — Move policy-domain internals behind package paths

### Change
Move into `src/policy/`:
- hitl
- policy_denial
- trust
- security_runtime
- tool_capabilities
- tool_runtime
- any directly policy-owned supporting modules

Keep flat compatibility shims.

### Tests
- old flat imports still work
- new package imports work
- policy package API unchanged

### Commit
`refactor: move policy modules behind package seam`

---

## Step 6 — Update internal callers to package imports

### Change
Now that implementation modules live under package paths and shims exist, migrate repo-internal imports to prefer:
- `src.evidence...`
- `src.deliverables...`
- `src.execution...`
- `src.implement...`
- `src.policy...`

Do not remove shims yet.

### Tests
- full suite stays green
- spot-check key internal modules for package import usage

### Commit
`refactor: migrate internal imports to domain packages`

---

## Step 7 — Remove compatibility shims and update architecture docs

### Change
Only after all callers are migrated:
- remove leftover flat compatibility shims
- update domain map and any architecture/manifests
- ensure package entrypoints are the canonical API

### Tests
- full suite green without shims
- import tests updated to new canonical paths where appropriate

### Commit
`refactor: remove flat module shims and finalize domain migration`

---

## Acceptance criteria
- domain implementations live under their bounded-context packages
- compatibility is preserved during migration, not broken midstream
- internal callers prefer package imports before shim removal
- final cleanup removes transitional duplication safely

---

## Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM15 Step 1 only.

Context:
- MM16 has already been completed before starting MM15.
- MM12 introduced package seams; MM15 now migrates real implementations behind them.
- IMPORTANT: use migration shims first. Do not do a big-bang move/delete step.

Rules:
- TDD first
- never build
- tests only
- one commit for this step only
- stop after the commit
- do not continue to Step 2 automatically

Step 1 goal:
Move evidence internals behind the src.evidence package while preserving backward compatibility.

Required changes:
1. Move evidence implementation modules into src/evidence/
2. Leave thin compatibility shims at old flat module paths
3. Keep src.evidence package exports working
4. Do not remove old paths yet

Tests to add/update:
- old flat imports still work
- new package module imports work
- src.evidence package exports still work

Commit message:
refactor: move evidence modules behind package seam

When done, stop and report in this structure:

Step completed
- milestone: MM15
- step: 1
- commit:
- tests run:
- result:

What changed
- bullet list of code changes
- bullet list of tests added/updated

Notes for review
- tradeoffs
- anything deferred
```
