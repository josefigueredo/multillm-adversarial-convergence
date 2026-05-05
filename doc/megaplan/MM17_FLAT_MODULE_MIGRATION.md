# MM17 Plan — Complete Flat Module Migration

## Goal
Finish the domain decomposition that MM12/MM15 started.
Move the remaining ~22 flat `src/*.py` modules into their domain packages, then rename the 9 milestone-named test files to behavior-based names.

## Why this milestone exists
After MM15 the bounded-context packages exist and are populated, but `src/` still has ~22 modules sitting flat that clearly belong inside `evidence/`, `deliverables/`, `policy/`, `backends/`, or `workflows/`.
The result is a split identity: the domain architecture is declared but not fully enacted.
MM17 closes that gap without introducing new runtime behavior.

## Rules
- TDD first
- Never build
- One commit per step
- Stop after each step for review
- Move + shim first; caller cleanup second; shim deletion last
- No big-bang deletes

## Modules to migrate

### → `src/evidence/`
`agreement_artifacts`, `artifacts`, `certainty`, `comparison`,
`evaluation_artifacts`, `research_logs`, `reproducibility`,
`run_metadata_artifacts`, `scorer`, `semantic_eval`

### → `src/deliverables/`
`output_style`, `pdf_report`, `portfolio`, `reporting`

### → `src/policy/`
`audit_trail`, `constraints`, `dry_run`

### → `src/workflows/`
`run_finalize`, `run_state`

### → `src/backends/`
`backend_options`, `provider_instances`, `runtime_telemetry`

## Modules to keep flat (true orchestration core)
`cli`, `config`, `orchestrator`, `research_loop`,
`run_paths`, `run_io`, `explain`, `doctor`,
`prompts`, `strategy`

## Test files to rename (Step 7)
| Current name | Behavioral name |
|---|---|
| `test_mm13_step4_diagnostics.py` | `test_sandbox_backend_diagnostics_truthfulness.py` |
| `test_mm14_step1_run_subprocess.py` | `test_sandbox_backend_subprocess_contract.py` |
| `test_mm14_step2_container_run_subprocess.py` | `test_container_backend_subprocess.py` |
| `test_mm14_step3_executor_delegation.py` | `test_sandbox_executor_subprocess_delegation.py` |
| `test_mm14_step4_doctor_diagnostics.py` | `test_container_backend_readiness_diagnostics.py` |
| `test_mm16_step1_iteration_scope.py` | `test_iteration_workspace_scope_contract.py` |
| `test_mm16_step2_executor_iteration.py` | `test_sandbox_executor_iteration_workspace.py` |
| `test_mm16_step3_orchestrator_loop.py` | `test_orchestrator_iteration_workspace_wiring.py` |
| `test_mm16_step4_doctor_explain.py` | `test_iteration_workspace_diagnostics.py` |

## Test count baseline at MM17 start: 2563 passing

---

## Step 1 — Migrate evidence-domain flat modules

### Scope
Move 10 flat evidence-related modules into `src/evidence/`.

### Modules
`agreement_artifacts`, `artifacts`, `certainty`, `comparison`,
`evaluation_artifacts`, `research_logs`, `reproducibility`,
`run_metadata_artifacts`, `scorer`, `semantic_eval`

### Change
1. Copy each module into `src/evidence/<name>.py`
2. Update `src/evidence/__init__.py` to export everything the package already exports plus the new modules
3. Leave thin compatibility shims at each original flat path that re-export from the new location

### Tests
- old flat imports still resolve (`from src.scorer import ...`)
- new package imports work (`from src.evidence.scorer import ...`)
- `src.evidence` package exports still work
- full test suite stays green

### Commit
`refactor: move evidence-domain flat modules into src/evidence`

---

## Step 2 — Migrate deliverables-domain flat modules

### Scope
Move 4 flat deliverable-related modules into `src/deliverables/`.

### Modules
`output_style`, `pdf_report`, `portfolio`, `reporting`

### Change
1. Move each into `src/deliverables/<name>.py`
2. Update `src/deliverables/__init__.py`
3. Leave shims at old flat paths

### Tests
- old flat imports still work
- new package imports work
- `src.deliverables` package exports unchanged

### Commit
`refactor: move deliverables-domain flat modules into src/deliverables`

---

## Step 3 — Migrate policy and workflow flat modules

### Scope
Move 5 modules: 3 policy-domain + 2 workflow-domain.

### Modules
Policy: `audit_trail`, `constraints`, `dry_run`
Workflows: `run_finalize`, `run_state`

### Change
1. Move policy modules into `src/policy/`
2. Move workflow modules into `src/workflows/`
3. Update both package `__init__.py` files
4. Leave shims at all old flat paths

### Tests
- old flat imports still resolve
- new package imports work for both `src.policy.*` and `src.workflows.*`
- suite stays green

### Commit
`refactor: move policy and workflow flat modules into domain packages`

---

## Step 4 — Migrate backends-domain flat modules

### Scope
Move 3 flat modules used primarily by the backends layer.

### Modules
`backend_options`, `provider_instances`, `runtime_telemetry`

### Change
1. Move each into `src/backends/<name>.py`
2. Update `src/backends/__init__.py`
3. Leave shims at old flat paths

### Tests
- old flat imports still work
- new `src.backends.*` imports work
- backend and orchestrator tests stay green

### Commit
`refactor: move backends-domain flat modules into src/backends`

---

## Step 5 — Update internal callers to package imports

### Scope
Now that shims exist everywhere, migrate all repo-internal `from src.<flat_module>` imports to prefer the new canonical package paths.

### Target import prefixes
```
src.evidence.*
src.deliverables.*
src.policy.*
src.workflows.*
src.backends.*
```

### Do NOT touch
- External-facing public API imports (if any) — shims handle those
- Shims themselves
- Test files (they are covered by shims; leave them until Step 6)

### Tests
- full suite stays green
- grep confirms no `from src.scorer import`, `from src.audit_trail import`, etc. remain in production src files

### Commit
`refactor: migrate internal src imports to canonical domain packages`

---

## Step 6 — Remove compatibility shims; finalize domain tree

### Scope
With all internal callers migrated, delete the flat shim files.
Update any test imports that still use old flat paths.

### Change
1. Delete all shim files created in Steps 1–4
2. Update any test file imports that still target the old flat paths
3. Confirm `src/` flat layer now contains only the 10 true-core modules

### Final expected flat layer in `src/`
```
cli.py
config.py
doctor.py
dry_run.py  ← already in policy/ after Step 3; shim deleted here
explain.py
orchestrator.py
prompts.py
research_loop.py
run_io.py
run_paths.py
strategy.py
__init__.py
```
(Plus all domain package subdirectories.)

### Tests
- full suite green without shims
- import tests updated to canonical paths where appropriate

### Commit
`refactor: remove flat module shims; finalize domain tree cleanup`

---

## Step 7 — Rename milestone-named test files to behavior-based names

### Scope
Rename the 9 `test_mm*.py` test files.
These names encode implementation history, not behavior.
A test suite should be readable by anyone unfamiliar with the milestone numbering.

### Renames
| Old | New |
|---|---|
| `test_mm13_step4_diagnostics.py` | `test_sandbox_backend_diagnostics_truthfulness.py` |
| `test_mm14_step1_run_subprocess.py` | `test_sandbox_backend_subprocess_contract.py` |
| `test_mm14_step2_container_run_subprocess.py` | `test_container_backend_subprocess.py` |
| `test_mm14_step3_executor_delegation.py` | `test_sandbox_executor_subprocess_delegation.py` |
| `test_mm14_step4_doctor_diagnostics.py` | `test_container_backend_readiness_diagnostics.py` |
| `test_mm16_step1_iteration_scope.py` | `test_iteration_workspace_scope_contract.py` |
| `test_mm16_step2_executor_iteration.py` | `test_sandbox_executor_iteration_workspace.py` |
| `test_mm16_step3_orchestrator_loop.py` | `test_orchestrator_iteration_workspace_wiring.py` |
| `test_mm16_step4_doctor_explain.py` | `test_iteration_workspace_diagnostics.py` |

### Change
- `git mv` each file to its new name
- Update the module docstring inside each file to remove the "MM1X Step Y" title line
- Do not change any test logic

### Tests
- all tests still collected and pass after rename
- no test IDs change (pytest collects by function name, not file name)

### Commit
`refactor: rename milestone-named tests to describe behavior`

---

## Acceptance criteria
- `src/` flat layer contains exactly the 10 true-core modules plus domain package subdirectories
- all 22 domain modules live inside their bounded-context packages
- no flat shims remain
- internal imports use canonical package paths
- no `test_mm*.py` files remain in the test suite
- full test suite passes (target: ≥ 2563)

---

## Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 1 only.

Context:
- MM15 completed domain package creation (evidence, deliverables, execution, implement, policy, workflows).
- ~22 flat src/*.py modules still live outside any package but clearly belong inside domain packages.
- MM17 completes the migration using the same move+shim pattern as MM15.
- IMPORTANT: move + shim first. Do NOT delete old paths yet.

Rules:
- TDD first
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 2 automatically

Step 1 goal:
Move the 10 evidence-domain flat modules into src/evidence/ while preserving backward compatibility.

Modules to move into src/evidence/:
- agreement_artifacts
- artifacts
- certainty
- comparison
- evaluation_artifacts
- research_logs
- reproducibility
- run_metadata_artifacts
- scorer
- semantic_eval

Required changes:
1. Move each module into src/evidence/<name>.py
2. Leave a thin compatibility shim at the old flat path (e.g. src/scorer.py) that re-exports from src.evidence.scorer
3. Update src/evidence/__init__.py to include new exports where appropriate
4. Do NOT delete the shims yet

Tests to add/update:
- old flat imports still resolve
- new src.evidence.* imports work
- src.evidence package exports unchanged
- full suite stays green

Commit message:
refactor: move evidence-domain flat modules into src/evidence

When done, stop and report in this structure:

Step completed
- milestone: MM17
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
