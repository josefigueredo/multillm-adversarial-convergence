# MM17 Plan — Complete Flat Module Migration (v2)

> Revised after Codex critique of v1.
> Changes from v1: dry_run contradiction fixed; all step prompts in one file;
> ownership audit table added; __init__.py policy defined per package;
> TDD contracts made explicit; circular import checks added; behavioral
> acceptance criteria added; provider_instances and runtime_telemetry kept flat
> after architectural review; doc truth step added.

## Goal
Finish the domain decomposition started in MM12/MM15.
Move the remaining 20 flat `src/*.py` modules into their domain packages,
correct package docstring claims about migration completeness, then rename
the 9 milestone-named test files to behavior-based names.

## Why this milestone exists
After MM15 the domain packages exist and are populated, but 20 modules still
live flat in `src/`. The result is a split identity: the domain architecture
is declared but not enacted. MM17 closes that gap and makes the `src/` tree
read cleanly as: core orchestration layer + domain packages.

## Rules
- TDD first — explicit contract tests, not just "suite green"
- Never build
- One commit per step
- Stop after each step for review
- Move + shim first; caller migration second; shim deletion last
- No big-bang deletes
- Every step must verify no new circular imports

---

## Pre-migration ownership audit

| Module | Target package | Ownership rationale | Key production callers | Risk |
|---|---|---|---|---|
| `agreement_artifacts` | `src/evidence/` | research agreement artifacts | none (test only) | low |
| `artifacts` | `src/evidence/` | research artifact containers | `orchestrator`, `research_loop` | medium |
| `certainty` | `src/evidence/` | confidence scoring primitives | test only | low |
| `comparison` | `src/evidence/` | multi-run comparison artifacts | `research_loop`, `run_io` | low |
| `evaluation_artifacts` | `src/evidence/` | evaluation result structs | `research_loop` | low |
| `research_logs` | `src/evidence/` | per-iteration evidence log | `research_loop` | low |
| `reproducibility` | `src/evidence/` | deterministic run analysis | `doctor`, `run_finalize` | low |
| `run_metadata_artifacts` | `src/evidence/` | run-level metadata structs | `orchestrator` | low |
| `scorer` | `src/evidence/` | convergence scoring | `research_loop`, `orchestrator`, others | medium |
| `semantic_eval` | `src/evidence/` | semantic similarity evaluation | `research_loop`, `scorer` | low |
| `output_style` | `src/deliverables/` | output formatting primitives | `reporting`, `pdf_report`, others | medium |
| `pdf_report` | `src/deliverables/` | PDF export | `run_finalize`, `cli` | low |
| `portfolio` | `src/deliverables/` | run portfolio aggregation | `run_finalize`, `cli` | low |
| `reporting` | `src/deliverables/` | report generation | `run_finalize`, `orchestrator` | low |
| `audit_trail` | `src/policy/` | runtime audit write abstraction | `implement/`, `orchestrator`, tests | high |
| `constraints` | `src/policy/` | constraint policy structs | `config`, `orchestrator` | low |
| `dry_run` | `src/policy/` | dry-run execution mode | `cli`, `orchestrator` | low |
| `run_finalize` | `src/workflows/` | run completion orchestration | `orchestrator` only | low |
| `run_state` | `src/workflows/` | base run context model | `implement/` loops | medium |
| `backend_options` | `src/backends/` | call option construction | `implement/` refiners | low |

## Modules kept flat (true orchestration core — do not move)

These modules are used by `cli.py`, `orchestrator.py`, `strategy.py` directly
and are cross-cutting runtime utilities, not domain internals.

```
cli.py               config.py            doctor.py
explain.py           orchestrator.py      prompts.py
provider_instances.py  research_loop.py   run_io.py
run_paths.py         runtime_telemetry.py  strategy.py
```

`provider_instances` and `runtime_telemetry` were candidates but are
**kept flat**: `provider_instances` is imported by `cli.py` and `strategy.py`
(true orchestration core); `runtime_telemetry` is imported by `orchestrator.py`.
Moving them into `src/backends/` would make core files depend on a backend
internal — wrong dependency direction.

---

## `__init__.py` policy per package

Each package has a distinct surface type. Agents must follow the rule for
the package they are touching in each step.

| Package | Surface type | Rule for moved modules |
|---|---|---|
| `src/evidence/` | Curated public API | Re-export key symbols in `__init__.py` under named sections |
| `src/deliverables/` | Curated public API | Same: add named section with key symbols |
| `src/policy/` | Curated public API | Same: add `audit_trail`, `constraints`, `dry_run` exports |
| `src/workflows/` | Namespace only | Do NOT re-export at package level; callers use `from src.workflows.run_state import ...` |
| `src/backends/` | Registration surface | Add `backend_options` exports explicitly |

---

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

---

## Test count baseline at MM17 start: 2563 passing

---

## Step 1 — Correct package docstring truth drift

### Why this step comes first
`src/evidence/__init__.py`, `src/deliverables/__init__.py`, and
`src/policy/__init__.py` contain the claim "flat-module imports were removed
in MM15 Step 7." That claim is false for the modules being migrated in MM17
(scorer, output_style, audit_trail, etc. are still flat).

This is a truthfulness violation under the repo's own operator rules.
Fix it before touching any module placement, so the repo stays honest at
every commit boundary.

### Change
Update the three `__init__.py` docstrings:
- Remove or qualify the blanket "flat-module imports were removed in MM15 Step 7" claim
- Replace with accurate language like:
  "MM15 migrated [list]. MM17 will complete migration of remaining domain modules."
- `src/workflows/__init__.py`: update the one-liner to reflect it is a namespace package, not a curated API

### No module moves in this step
No `__all__`, no shims, no module moves. Docs only.

### Tests
- `python -c "import src"` succeeds
- `python -c "import src.evidence; import src.deliverables; import src.policy"` succeeds
- full suite stays green

### Commit
`docs: correct package docstring claims about flat-module migration completeness`

---

## Step 2 — Move evidence-domain flat modules

### Scope
Move 10 flat evidence-related modules into `src/evidence/`.

### Modules
`agreement_artifacts`, `artifacts`, `certainty`, `comparison`,
`evaluation_artifacts`, `research_logs`, `reproducibility`,
`run_metadata_artifacts`, `scorer`, `semantic_eval`

### Change
1. Copy each module into `src/evidence/<name>.py`
2. Leave a thin shim at the old flat path: `from src.evidence.<name> import *`
   plus an explicit `__all__` re-export matching the original module's public symbols
3. Update `src/evidence/__init__.py` with a new named section that re-exports
   key public symbols from each moved module (follow the existing section style)
4. Do NOT delete shims yet

### Explicit contract tests to add (per module)
For each moved module:
- `from src.<name> import <KeyClass>` resolves (shim works)
- `from src.evidence.<name> import <KeyClass>` resolves (new path works)
- `src.<name>.<KeyClass> is src.evidence.<name>.<KeyClass>` — same object (no duplication)

### Circular import check (required)
After the step:
```
python -c "import src; import src.evidence"
```
Must complete without `ImportError` or `CircularImportError`.

### Commit
`refactor: move evidence-domain flat modules into src/evidence`

---

## Step 3 — Move deliverables-domain flat modules

### Scope
Move 4 flat deliverable-related modules into `src/deliverables/`.

### Modules
`output_style`, `pdf_report`, `portfolio`, `reporting`

### Change
1. Move each into `src/deliverables/<name>.py`
2. Leave shims at old flat paths
3. Update `src/deliverables/__init__.py` with new named section following package style

### Explicit contract tests to add
For each module:
- old flat import resolves
- `src.deliverables.<name>` import resolves
- same object identity through shim

### Circular import check (required)
```
python -c "import src; import src.deliverables"
```

### Commit
`refactor: move deliverables-domain flat modules into src/deliverables`

---

## Step 4 — Move policy, workflow, and backends flat modules

### Scope
6 modules across three packages in one step (all small / low-risk).

### Modules

**→ `src/policy/`**: `audit_trail`, `constraints`, `dry_run`

`audit_trail` is the highest-risk module in the whole milestone (12 importers).
Key exported symbols: `AuditTrailWriter`, `NullAuditTrailWriter`.
Both must be re-exported from `src/policy/__init__.py` because they are used
directly in tests and in `src/implement/` via the flat path.

**→ `src/workflows/`**: `run_finalize`, `run_state`

`src/workflows/__init__.py` is a **namespace only** — do NOT re-export these
at package level. Callers use direct submodule paths.

**→ `src/backends/`**: `backend_options`

Add `apply_backend_capabilities` and `build_call_options` to
`src/backends/__init__.py` exports.

### Change
1. Move each module to its target package
2. Leave shims at all old flat paths
3. Update `src/policy/__init__.py` and `src/backends/__init__.py` per the
   __init__.py policy table above
4. Do NOT update `src/workflows/__init__.py` beyond a minor docstring note

### Explicit contract tests to add
For each of the 6 modules:
- old flat import resolves
- new package import resolves
- same object identity through shim
- specifically for `audit_trail`: `from src.audit_trail import AuditTrailWriter`
  and `from src.policy.audit_trail import AuditTrailWriter` yield the same class

### Circular import check (required)
```
python -c "import src; import src.policy; import src.workflows; import src.backends"
```
The `audit_trail` move in particular risks a cycle if `src/policy/` ends up
importing `src/implement/` or vice versa. Verify the direction stays:
`implement → policy` only, never `policy → implement`.

### Commit
`refactor: move policy, workflow, and backends flat modules into domain packages`

---

## Step 5 — Migrate internal callers to canonical package imports

### Scope
Update all production `src/` imports to use canonical package paths.
Shims are still present; this step updates callers so shim deletion in Step 6
has no callers left to break.

### Target import mappings

```
src.agreement_artifacts  → src.evidence.agreement_artifacts
src.artifacts            → src.evidence.artifacts
src.certainty            → src.evidence.certainty
src.comparison           → src.evidence.comparison
src.evaluation_artifacts → src.evidence.evaluation_artifacts
src.research_logs        → src.evidence.research_logs
src.reproducibility      → src.evidence.reproducibility
src.run_metadata_artifacts → src.evidence.run_metadata_artifacts
src.scorer               → src.evidence.scorer
src.semantic_eval        → src.evidence.semantic_eval

src.output_style  → src.deliverables.output_style
src.pdf_report    → src.deliverables.pdf_report
src.portfolio     → src.deliverables.portfolio
src.reporting     → src.deliverables.reporting

src.audit_trail   → src.policy.audit_trail
src.constraints   → src.policy.constraints
src.dry_run       → src.policy.dry_run

src.run_finalize  → src.workflows.run_finalize
src.run_state     → src.workflows.run_state

src.backend_options → src.backends.backend_options
```

### Do NOT touch
- Test files (still covered by shims; updated if needed in Step 6)
- Shim files themselves
- True-core flat modules

### Required verifications
1. Grep confirms no old flat import paths remain in `src/` production files
   (excluding shim files and the 12 true-core flat modules)
2. `python -c "import src"` still succeeds
3. Full suite stays green

### Circular import check (required)
After all import updates:
```
python -c "
import src.evidence, src.deliverables, src.policy, src.workflows, src.backends
import src.orchestrator, src.research_loop, src.cli
"
```
Must complete without error.

### Commit
`refactor: migrate internal src imports to canonical domain packages`

---

## Step 6 — Remove compatibility shims; finalize flat layer

### Scope
Delete all 20 shim files. Update any test file imports still using old flat
paths. Confirm the final `src/` flat layer.

### Shims to delete
```
src/agreement_artifacts.py   src/artifacts.py          src/certainty.py
src/comparison.py            src/evaluation_artifacts.py src/research_logs.py
src/reproducibility.py       src/run_metadata_artifacts.py src/scorer.py
src/semantic_eval.py         src/output_style.py       src/pdf_report.py
src/portfolio.py             src/reporting.py          src/audit_trail.py
src/constraints.py           src/dry_run.py            src/run_finalize.py
src/run_state.py             src/backend_options.py
```

### Final expected flat layer in `src/`
```
__init__.py           cli.py               config.py
doctor.py             explain.py           orchestrator.py
prompts.py            provider_instances.py  research_loop.py
run_io.py             run_paths.py         runtime_telemetry.py
strategy.py
```
(12 modules + `__init__.py` = 13 files, plus all domain package subdirectories.)

### Change
1. Delete all 20 shim files
2. grep `tests/` for any flat-path imports; update to canonical package paths
3. Update `src/evidence/__init__.py`, `src/deliverables/__init__.py`,
   `src/policy/__init__.py` docstrings: replace "MM15 migrated …" note with
   "MM17 completed migration of remaining domain modules"

### Required verifications
1. `python -m pytest --collect-only -q` — same test count as before
2. Full suite green (target ≥ 2563)
3. `python -c "import src"` succeeds
4. No `src/<migrated_module>.py` files remain (grep confirms)

### Commit
`refactor: remove flat module shims; finalize domain tree cleanup`

---

## Step 7 — Rename milestone-named test files

### Scope
Rename 9 `test_mm*.py` files to behavior-based names.

### Why
Test files named after milestone numbers encode when they were written, not
what they test. Any contributor unfamiliar with the milestone history cannot
tell what the test covers. Behavior-based names are permanent.

### Renames
```
test_mm13_step4_diagnostics.py             → test_sandbox_backend_diagnostics_truthfulness.py
test_mm14_step1_run_subprocess.py          → test_sandbox_backend_subprocess_contract.py
test_mm14_step2_container_run_subprocess.py → test_container_backend_subprocess.py
test_mm14_step3_executor_delegation.py     → test_sandbox_executor_subprocess_delegation.py
test_mm14_step4_doctor_diagnostics.py      → test_container_backend_readiness_diagnostics.py
test_mm16_step1_iteration_scope.py         → test_iteration_workspace_scope_contract.py
test_mm16_step2_executor_iteration.py      → test_sandbox_executor_iteration_workspace.py
test_mm16_step3_orchestrator_loop.py       → test_orchestrator_iteration_workspace_wiring.py
test_mm16_step4_doctor_explain.py          → test_iteration_workspace_diagnostics.py
```

### Change
For each file:
1. `git mv <old_name> <new_name>`
2. Update the module docstring: remove the "MM1X Step Y —" prefix, keep the behavioral description
3. Do NOT change any test function, fixture, or assertion

### Required verifications
1. `python -m pytest --collect-only -q | wc -l` — test count unchanged
2. Full suite green
3. `ls tests/test_mm*.py` — returns nothing (no milestone-named files remain)

### Commit
`refactor: rename milestone-named tests to describe behavior`

---

## Acceptance criteria

### Structural
- `src/` flat layer contains exactly 13 files (12 modules + `__init__.py`)
- All 20 domain modules live inside bounded-context packages
- No flat shim files remain after Step 6
- No `test_mm*.py` files remain after Step 7

### Behavioral
- CLI boots: `python -m src.cli --help` succeeds from canonical paths
- No circular import regressions: the full import chain `import src; import src.orchestrator; import src.cli` completes without error
- No import-time side effects changed: `python -m pytest --collect-only` count unchanged from Step 6 through Step 7
- Package public API contracts explicitly preserved: shims guarantee backward compat through Step 5; Step 6 updates any remaining callers before deleting shims

### Truthfulness
- Package docstrings describe actual current content at each commit boundary
- No package claims migration completeness that has not yet happened
- Internal callers use canonical paths; no caller depends on shims after Step 5

### Tests
- Full suite ≥ 2563 passing at every step
- Contract tests exist for every moved module (old path, new path, object identity)
- Circular import check passes after every module-movement step

---

## Step 1 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 1 only.

Context:
- MM15 completed domain package creation. After MM15, three package __init__ files
  contain the claim "flat-module imports were removed in MM15 Step 7."
- That claim is false for ~20 modules that are still flat (scorer.py, audit_trail.py,
  output_style.py, etc.). This is a truthfulness violation under the repo's own
  operator rules.
- Step 1 fixes the docs before any module is moved, so the repo stays honest at
  every commit boundary.

Rules:
- No module moves in this step — docs only
- One commit for this step only
- Stop after the commit
- Do not continue to Step 2 automatically

Step 1 goal:
Correct the false completeness claims in three package __init__.py docstrings.

Files to update:
1. src/evidence/__init__.py
   - Remove or qualify "flat-module imports were removed in MM15 Step 7"
   - Replace with accurate description: list what MM15 actually migrated
     (references, provenance, provenance_artifacts, provenance_pipeline)
   - Note that evidence-domain flat modules (scorer, artifacts, certainty, etc.)
     remain flat and will be migrated in MM17

2. src/deliverables/__init__.py
   - Same treatment: list what MM15 migrated (pipeline, classes, citation_verification,
     export_bundle, report_exports)
   - Note deliverables-domain flat modules (output_style, pdf_report, portfolio,
     reporting) remain flat and will be migrated in MM17

3. src/policy/__init__.py
   - Same treatment: list what MM15 migrated (hitl, policy_denial, trust,
     security_runtime, tool_capabilities, tool_runtime, sandbox_executor)
   - Note policy-domain flat modules (audit_trail, constraints, dry_run)
     remain flat and will be migrated in MM17

4. src/workflows/__init__.py
   - Update from one-liner "Workflow state package — MM07" to a proper docstring
     that describes current contents and notes this is a namespace package
     (no re-exports at package level)

Verification:
- python -c "import src; import src.evidence; import src.deliverables; import src.policy; import src.workflows"
- Full suite still green (no logic changes, docs only)

Commit message:
docs: correct package docstring claims about flat-module migration completeness

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 1
- commit:
- tests run:
- result:

What changed
- bullet list of docstring changes per file

Notes for review
- any wording choices made
- anything deferred
```

---

## Step 2 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 2 only.

Context:
- MM17 Step 1 is complete. Package docstrings are now honest.
- Step 2 moves 10 evidence-domain flat modules into src/evidence/ using
  the same move+shim pattern as MM15.

Rules:
- TDD first — write contract tests before or alongside the moves
- One commit for this step only
- Stop after the commit
- Do not continue to Step 3 automatically

Step 2 goal:
Move 10 evidence-domain flat modules into src/evidence/ with shims at old paths.

Modules to move into src/evidence/:
  agreement_artifacts, artifacts, certainty, comparison,
  evaluation_artifacts, research_logs, reproducibility,
  run_metadata_artifacts, scorer, semantic_eval

Required changes:
1. Copy each module to src/evidence/<name>.py
2. Leave a thin shim at each old flat path:
     from src.evidence.<name> import *  # plus explicit re-exports if needed
3. Update src/evidence/__init__.py: add a new named section that re-exports
   key public symbols from each moved module (follow existing section style)
4. Do NOT delete shims yet

Contract tests required per moved module:
  - from src.<name> import <KeySymbol>  →  resolves (shim works)
  - from src.evidence.<name> import <KeySymbol>  →  resolves (new path)
  - src.<name>.<KeySymbol> is src.evidence.<name>.<KeySymbol>  →  True (no duplication)

Circular import check (required after all moves):
  python -c "import src; import src.evidence"
  Must complete without ImportError or circular import error.

Commit message:
refactor: move evidence-domain flat modules into src/evidence

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 2
- commit:
- tests run:
- result:

What changed
- bullet list of moved modules
- bullet list of contract tests added
- evidence/__init__.py changes

Notes for review
- any import topology concerns found
- anything deferred
```

---

## Step 3 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 3 only.

Context:
- MM17 Steps 1 and 2 complete. Evidence-domain modules are in src/evidence/ with shims.
- Step 3 moves 4 deliverables-domain flat modules.

Rules:
- TDD first
- One commit for this step only
- Stop after the commit
- Do not continue to Step 4 automatically

Step 3 goal:
Move 4 deliverables-domain flat modules into src/deliverables/ with shims at old paths.

Modules to move into src/deliverables/:
  output_style, pdf_report, portfolio, reporting

Required changes:
1. Move each into src/deliverables/<name>.py
2. Leave shims at old flat paths
3. Update src/deliverables/__init__.py: add named section with key exports
   following existing package style

Contract tests required per module:
  - old flat import resolves
  - src.deliverables.<name> import resolves
  - same object identity through shim

Circular import check:
  python -c "import src; import src.deliverables"

Commit message:
refactor: move deliverables-domain flat modules into src/deliverables

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 3
- commit:
- tests run:
- result:

What changed
- bullet list of moved modules
- contract tests added

Notes for review
- any concerns
- anything deferred
```

---

## Step 4 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 4 only.

Context:
- MM17 Steps 1–3 complete. This is the last module-movement step.
- 6 modules across three packages. audit_trail is the highest-risk (12 importers).

Rules:
- TDD first
- One commit for this step only
- Stop after the commit
- Do not continue to Step 5 automatically

Step 4 goal:
Move policy-domain, workflow-domain, and backends-domain flat modules into their packages.

Modules → src/policy/:
  audit_trail, constraints, dry_run

  IMPORTANT for audit_trail:
  - AuditTrailWriter and NullAuditTrailWriter must be re-exported from
    src/policy/__init__.py because they are used across implement/, tests, etc.
  - Shim at src/audit_trail.py must cover all currently-imported symbols

Modules → src/workflows/:
  run_finalize, run_state

  IMPORTANT: src/workflows/__init__.py is a NAMESPACE ONLY — do NOT re-export
  these at package level. Callers use direct submodule paths:
    from src.workflows.run_state import BaseContext
  Do not change src/workflows/__init__.py beyond a minor docstring note.

Modules → src/backends/:
  backend_options

  Add apply_backend_capabilities and build_call_options to src/backends/__init__.py.

Required changes for all 6 modules:
1. Move to target package
2. Leave shim at old flat path
3. Update __init__.py per the rules above (policy+backends get exports; workflows does not)

Contract tests required per module:
  - old flat import resolves
  - new package import resolves
  - same object identity through shim
  - audit_trail specifically: both AuditTrailWriter and NullAuditTrailWriter must pass the identity check

Circular import check (critical for audit_trail):
  python -c "
  import src
  import src.policy, src.workflows, src.backends
  import src.implement.implement_loop
  import src.implement.document_loop
  import src.implement.plan_loop
  "
  Dependency direction must stay: implement → policy, never policy → implement.

Commit message:
refactor: move policy, workflow, and backends flat modules into domain packages

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 4
- commit:
- tests run:
- result:

What changed
- bullet list of moved modules per package
- contract tests added

Notes for review
- circular import checks passed/failed
- anything deferred
```

---

## Step 5 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 5 only.

Context:
- MM17 Steps 1–4 complete. All 20 domain modules are in their packages with flat shims.
- Step 5 updates all production src/ imports to canonical package paths so shims can
  be deleted safely in Step 6.

Rules:
- One commit for this step only
- Stop after the commit
- Do not continue to Step 6 automatically

Step 5 goal:
Update all repo-internal src/ imports to canonical domain package paths.

Canonical import mapping (replace left → right in all src/ production files):
  src.agreement_artifacts   → src.evidence.agreement_artifacts
  src.artifacts             → src.evidence.artifacts
  src.certainty             → src.evidence.certainty
  src.comparison            → src.evidence.comparison
  src.evaluation_artifacts  → src.evidence.evaluation_artifacts
  src.research_logs         → src.evidence.research_logs
  src.reproducibility       → src.evidence.reproducibility
  src.run_metadata_artifacts → src.evidence.run_metadata_artifacts
  src.scorer                → src.evidence.scorer
  src.semantic_eval         → src.evidence.semantic_eval
  src.output_style          → src.deliverables.output_style
  src.pdf_report            → src.deliverables.pdf_report
  src.portfolio             → src.deliverables.portfolio
  src.reporting             → src.deliverables.reporting
  src.audit_trail           → src.policy.audit_trail
  src.constraints           → src.policy.constraints
  src.dry_run               → src.policy.dry_run
  src.run_finalize          → src.workflows.run_finalize
  src.run_state             → src.workflows.run_state
  src.backend_options       → src.backends.backend_options

Do NOT touch:
  - Test files (leave for Step 6 if needed)
  - Shim files themselves
  - True-core flat modules: cli, config, orchestrator, research_loop, run_paths,
    run_io, explain, doctor, prompts, strategy, provider_instances, runtime_telemetry

Required verifications:
1. grep src/ (excluding shims and true-core) confirms no old flat import paths remain
2. Full suite green
3. Circular import chain check:
   python -c "
   import src.evidence, src.deliverables, src.policy, src.workflows, src.backends
   import src.orchestrator, src.research_loop, src.cli
   "

Commit message:
refactor: migrate internal src imports to canonical domain packages

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 5
- commit:
- tests run:
- result:

What changed
- files updated (list)
- summary of import paths changed by package

Notes for review
- any circular import concerns
- anything deferred
```

---

## Step 6 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 6 only.

Context:
- MM17 Steps 1–5 complete. All internal src/ imports use canonical paths.
- Step 6 removes all 20 shim files and updates any remaining test imports.

Rules:
- One commit for this step only
- Stop after the commit
- Do not continue to Step 7 automatically

Step 6 goal:
Delete all 20 compatibility shims. Update remaining test imports to canonical paths.
Finalize package docstrings to reflect completed migration.

Shim files to delete (all in src/):
  agreement_artifacts.py  artifacts.py          certainty.py
  comparison.py           evaluation_artifacts.py research_logs.py
  reproducibility.py      run_metadata_artifacts.py scorer.py
  semantic_eval.py        output_style.py       pdf_report.py
  portfolio.py            reporting.py          audit_trail.py
  constraints.py          dry_run.py            run_finalize.py
  run_state.py            backend_options.py

Steps:
1. Delete all 20 shim files
2. grep tests/ for any remaining flat-path imports; update to canonical package paths
3. Update src/evidence/__init__.py, src/deliverables/__init__.py, src/policy/__init__.py
   docstrings: the "MM17 will complete migration" note becomes "MM17 completed migration"

Final flat layer must be exactly:
  __init__.py  cli.py  config.py  doctor.py  explain.py
  orchestrator.py  prompts.py  provider_instances.py  research_loop.py
  run_io.py  run_paths.py  runtime_telemetry.py  strategy.py

Required verifications:
1. python -m pytest --collect-only -q — same count as before step
2. Full suite green (≥ 2563)
3. python -c "import src; import src.orchestrator; import src.cli" succeeds
4. ls src/*.py | grep -vE "(cli|config|doctor|explain|orchestrator|prompts|provider_instances|research_loop|run_io|run_paths|runtime_telemetry|strategy|__init__)" — returns nothing

Commit message:
refactor: remove flat module shims; finalize domain tree cleanup

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 6
- commit:
- tests run:
- result:

What changed
- list of shims deleted
- list of test imports updated

Notes for review
- any imports that needed special attention
- anything deferred
```

---

## Step 7 Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 7 only. This is the final MM17 step.

Context:
- MM17 Steps 1–6 complete. Domain tree is fully clean.
- Step 7 renames the 9 milestone-named test files to behavior-based names.
  Files named after milestone numbers encode when they were written, not what
  they test, and will confuse future contributors.

Rules:
- One commit for this step only
- This is the last MM17 step — report MM17 complete after the commit

Step 7 goal:
Rename 9 test_mm*.py files using git mv, update their module docstrings.

Renames (use git mv for each):
  test_mm13_step4_diagnostics.py             → test_sandbox_backend_diagnostics_truthfulness.py
  test_mm14_step1_run_subprocess.py          → test_sandbox_backend_subprocess_contract.py
  test_mm14_step2_container_run_subprocess.py → test_container_backend_subprocess.py
  test_mm14_step3_executor_delegation.py     → test_sandbox_executor_subprocess_delegation.py
  test_mm14_step4_doctor_diagnostics.py      → test_container_backend_readiness_diagnostics.py
  test_mm16_step1_iteration_scope.py         → test_iteration_workspace_scope_contract.py
  test_mm16_step2_executor_iteration.py      → test_sandbox_executor_iteration_workspace.py
  test_mm16_step3_orchestrator_loop.py       → test_orchestrator_iteration_workspace_wiring.py
  test_mm16_step4_doctor_explain.py          → test_iteration_workspace_diagnostics.py

For each file:
1. git mv <old> <new>
2. Update the module docstring: remove "MM1X Step Y —" prefix, keep behavioral description
3. Do NOT change any test function, fixture, or assertion

Required verifications:
1. python -m pytest --collect-only -q | wc -l  →  same count as before
2. Full suite green
3. ls tests/test_mm*.py  →  no output (no milestone-named files remain)

Commit message:
refactor: rename milestone-named tests to describe behavior

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 7 (FINAL)
- commit:
- tests run:
- result:

What changed
- list of renames

MM17 complete after this step.
Report final test count and confirm acceptance criteria met.
```
