# MM16 Plan — Per-Iteration Workspace Isolation

## Goal
Make `sandbox.scope: iteration` a real runtime isolation option with explicit per-iteration workspace semantics.

## Why this milestone exists
After MM14, sandbox backends can execute subprocesses. MM16 then sharpens workspace isolation so a run can isolate each iteration instead of sharing one workspace across the whole run.

## Recommended order note
MM16 should happen **before MM15 file migration** because it deepens runtime truth rather than structural churn.

## Rules
- TDD first
- Never build
- One commit per step
- Stop after each step for review
- Keep run-scope behavior working while adding iteration-scope behavior

## Concrete workspace contract
Unless the codebase already forces a better shape during implementation, prefer:
- run scope: `output/<run>/.workspace/`
- iteration scope: `output/<run>/.workspace/iter_<N>/`

The exact path can change if the repo architecture suggests something better, but the contract must be:
- explicit
- documented
- tested

---

## Step 1 — Add iteration scope to config and backend interface

### Change
- add `iteration` to `VALID_SANDBOX_SCOPES`
- extend backend workspace-preparation contract to accept iteration context, e.g.:
  - `prepare_workspace(*, iteration: int | None = None) -> Path`
- update both backends to accept the new signature without breaking run-scope behavior

### Tests
- config accepts `sandbox.scope: iteration`
- config rejects unknown scope values
- both backends accept `iteration=` argument
- run-scope default still works unchanged

### Commit
`feat: add iteration sandbox scope contract`

---

## Step 2 — Define and implement concrete iteration workspace path layout

### Change
Implement real path behavior for both backends:
- run scope → shared workspace path
- iteration scope → per-iteration workspace path

For container mode:
- host iteration workspace and container iteration workspace mapping must both be explicit
- authoritative returned path must still be the execution-side path

### Tests
- local_process run scope returns shared path
- local_process iteration scope returns per-iteration path
- container run scope returns shared container path
- container iteration scope returns per-iteration container path
- host-side directories are created correctly

### Commit
`feat: implement iteration workspace layout`

---

## Step 3 — Wire executor and transient sandbox support

### Change
Update `SandboxExecutor` so:
- it forwards `iteration=` to backend workspace preparation when relevant
- transient sandbox creation paths also honor configured scope semantics

### Tests
- executor forwards iteration correctly
- transient sandbox behavior respects iteration scope
- authoritative workspace path updates correctly for both backends

### Commit
`feat: wire iteration workspace handling through executor`

---

## Step 4 — Wire orchestrator loop and audit events

### Change
Update orchestrator runtime so:
- run setup does not eagerly lock in a shared workspace when scope is iteration
- before each iteration, workspace preparation is called with the current iteration number
- audit trail records iteration workspace information explicitly

### Tests
- iteration scope causes per-iteration workspace prep in the loop
- run scope still behaves as before
- audit events reflect iteration workspace truth

### Commit
`feat: use per-iteration workspace isolation in orchestrator`

---

## Step 5 — Doctor, explain, and docs alignment

### Change
Update diagnostics/docs to say:
- whether sandbox scope is run or iteration
- what workspace layout that implies
- what isolation guarantee it changes
- backend-specific caveats if needed

### Tests
- doctor output reflects iteration scope
- explain output reflects iteration scope
- wording is honest and not overclaimed

### Commit
`docs: align iteration workspace isolation diagnostics`

---

## Acceptance criteria
- `sandbox.scope: iteration` is a real runtime option
- per-iteration workspace path is explicit and tested
- both local and container backends respect the scope
- orchestrator uses per-iteration preparation when configured
- doctor/explain/docs describe the behavior truthfully

---

## Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM16 Step 1 only.

Context:
- MM14 has already been completed before starting MM16.
- This milestone makes sandbox.scope: iteration a real runtime option.
- Keep runtime truth explicit and tested.

Rules:
- TDD first
- never build
- tests only
- one commit for this step only
- stop after the commit
- do not continue to Step 2 automatically

Step 1 goal:
Add iteration scope to the config contract and backend workspace-preparation interface.

Required changes:
1. Add `iteration` to VALID_SANDBOX_SCOPES
2. Update the sandbox backend interface so prepare_workspace accepts iteration context
3. Update both local and container backends to accept the new signature without breaking existing run-scope behavior

Tests to add/update:
- config accepts sandbox.scope: iteration
- invalid scope values still fail
- both backends accept iteration= argument
- run-scope default behavior still works

Commit message:
feat: add iteration sandbox scope contract

When done, stop and report in this structure:

Step completed
- milestone: MM16
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
