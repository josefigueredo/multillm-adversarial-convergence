# MM17 Plan — Complete Flat Module Migration (v3)

> Revised after two rounds of Codex critique.
>
> v1 → v2: fixed dry_run contradiction; embedded all prompts; added ownership
> table; defined __init__.py policy; added contract tests and circular-import
> checks; kept provider_instances and runtime_telemetry flat.
>
> v2 → v3: corrected "all resolved" overclaim; Step 4 split into 4a (policy)
> and 4b (workflows + backends) for causal isolation; truth-drift scope
> corrected to 3 packages (implement/ and execution/ claims are accurate);
> backend_options __init__.py policy changed to namespace-only (avoids
> circular import with backends registration surface).

## Goal
Finish the domain decomposition started in MM12/MM15.
Move the remaining 20 flat `src/*.py` modules into their domain packages,
correct the three false package docstring claims, then rename the 9
milestone-named test files to behavior-based names.

## Why this milestone exists
After MM15 the domain packages exist and are populated, but 20 modules still
live flat in `src/`. The result is a split identity: the domain architecture
is declared but not enacted. MM17 closes that gap without introducing new
runtime behavior.

## Rules
- Never build
- One commit per step
- Stop after each step for review
- Move + shim first; caller migration second; shim deletion last
- No big-bang deletes
- Every module-movement step must run the circular import verification chain

---

## Truth-drift clarification

Five packages contain the phrase "flat-module imports were removed in MM15 Step 7."

- `src/implement/__init__.py` — **accurate**: MM15 fully migrated implement; no flat siblings remain
- `src/execution/__init__.py` — **accurate**: MM15 fully migrated execution; no flat siblings remain
- `src/evidence/__init__.py` — **false**: scorer, artifacts, certainty, and 7 others are still flat
- `src/deliverables/__init__.py` — **false**: output_style, pdf_report, portfolio, reporting still flat
- `src/policy/__init__.py` — **false**: audit_trail, constraints, dry_run still flat

Step 1 corrects only the three false claims. The two accurate claims are left untouched.

---

## Pre-migration ownership audit

| Module | Target | Ownership rationale | Key production callers | Risk |
|---|---|---|---|---|
| `agreement_artifacts` | `src/evidence/` | research agreement artifacts | none | low |
| `artifacts` | `src/evidence/` | research artifact containers | `orchestrator`, `research_loop` | medium |
| `certainty` | `src/evidence/` | confidence scoring primitives | `research_loop` | low |
| `comparison` | `src/evidence/` | multi-run comparison artifacts | `research_loop`, `run_io` | low |
| `evaluation_artifacts` | `src/evidence/` | evaluation result structs | `research_loop` | low |
| `research_logs` | `src/evidence/` | per-iteration evidence log | `research_loop` | low |
| `reproducibility` | `src/evidence/` | deterministic run analysis | `doctor`, `run_finalize` | low |
| `run_metadata_artifacts` | `src/evidence/` | run-level metadata structs | `orchestrator` | low |
| `scorer` | `src/evidence/` | convergence scoring | `research_loop`, `orchestrator` | medium |
| `semantic_eval` | `src/evidence/` | semantic similarity evaluation | `research_loop`, `scorer` | low |
| `output_style` | `src/deliverables/` | output formatting primitives | `reporting`, `pdf_report` | medium |
| `pdf_report` | `src/deliverables/` | PDF export | `run_finalize`, `cli` | low |
| `portfolio` | `src/deliverables/` | run portfolio aggregation | `run_finalize`, `cli` | low |
| `reporting` | `src/deliverables/` | report generation | `run_finalize`, `orchestrator` | low |
| `audit_trail` | `src/policy/` | runtime audit write abstraction | `implement/` (3 files), `orchestrator`, 8 tests | **high** |
| `constraints` | `src/policy/` | constraint policy structs | `config`, `orchestrator` | low |
| `dry_run` | `src/policy/` | dry-run execution mode | `cli`, `orchestrator` | low |
| `run_finalize` | `src/workflows/` | run completion orchestration | `orchestrator` only | low |
| `run_state` | `src/workflows/` | base run context model | `implement/` loops | medium |
| `backend_options` | `src/backends/` | call option construction for backends | `implement/` refiners | low |

## Modules kept flat (true orchestration core — do not move)

```
cli.py                config.py             doctor.py
explain.py            orchestrator.py       prompts.py
provider_instances.py research_loop.py      run_io.py
run_paths.py          runtime_telemetry.py  strategy.py
```

`provider_instances` is imported by `cli.py` and `strategy.py`.
`runtime_telemetry` is imported by `orchestrator.py`.
Both depend on `src.backends` as a sibling. Moving them into `src/backends/`
would invert the dependency direction (backend internal depending on core
runtime). They stay flat.

---

## `__init__.py` policy per package

| Package | Surface type | Policy for moved modules |
|---|---|---|
| `src/evidence/` | Curated public API | Re-export key symbols in `__init__.py` under a named section |
| `src/deliverables/` | Curated public API | Same: add named section with key symbols |
| `src/policy/` | Curated public API | Add `audit_trail` exports (`AuditTrailWriter`, `NullAuditTrailWriter`); `constraints` and `dry_run` key types |
| `src/workflows/` | Namespace only | Do NOT re-export. Callers use `from src.workflows.run_state import BaseContext` |
| `src/backends/` | Registration surface | Do NOT add `backend_options` to `__init__.py`. `backend_options` imports `from .backends import Backend, CallOptions` at module level; adding it to `__init__.py` creates a circular import during package init. Callers use `from src.backends.backend_options import ...` directly |

---

## Test files to rename (Step 8)

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

## Step 1 — Correct false package docstring claims

### Why first
Three packages contain the false claim "flat-module imports were removed in MM15
Step 7" when their flat siblings still exist. Correcting this before any module
moves ensures the repo is honest at every commit boundary.

Do NOT change `src/implement/__init__.py` or `src/execution/__init__.py` —
those claims are accurate.

### Change
1. `src/evidence/__init__.py` — qualify the claim to list exactly what MM15 migrated
   (`references`, `provenance`, `provenance_artifacts`, `provenance_pipeline`);
   explicitly note that `scorer`, `artifacts`, `certainty`, `comparison`,
   `evaluation_artifacts`, `research_logs`, `reproducibility`,
   `run_metadata_artifacts`, `semantic_eval`, `agreement_artifacts`
   are evidence-domain flat modules not yet migrated (MM17 will do this)
2. `src/deliverables/__init__.py` — list what MM15 migrated
   (`pipeline`, `classes`, `citation_verification`, `export_bundle`, `report_exports`);
   note `output_style`, `pdf_report`, `portfolio`, `reporting` remain flat until MM17
3. `src/policy/__init__.py` — list what MM15 migrated
   (`hitl`, `policy_denial`, `trust`, `security_runtime`, `tool_capabilities`,
   `tool_runtime`, `sandbox_executor`);
   note `audit_trail`, `constraints`, `dry_run` remain flat until MM17

### No module moves, no __init__ export changes
Documentation only. No logic changes.

### Tests
```
python -c "import src; import src.evidence; import src.deliverables; import src.policy"
```
Full suite stays green.

### Commit
`docs: correct false flat-module migration claims in evidence, deliverables, policy`

---

## Step 2 — Move evidence-domain flat modules

### Scope
10 modules into `src/evidence/`.

### Modules
`agreement_artifacts`, `artifacts`, `certainty`, `comparison`,
`evaluation_artifacts`, `research_logs`, `reproducibility`,
`run_metadata_artifacts`, `scorer`, `semantic_eval`

### Change
1. Copy each module to `src/evidence/<name>.py`
2. Shim at old flat path:
   ```python
   # src/scorer.py — compatibility shim; canonical: src.evidence.scorer
   from src.evidence.scorer import *  # noqa: F401, F403
   ```
3. Update `src/evidence/__init__.py`: add a named section re-exporting key public
   symbols from each moved module (follow existing section style)
4. Do NOT delete shims yet

### Contract tests required (for each module)
- `from src.<name> import <KeySymbol>` resolves — shim works
- `from src.evidence.<name> import <KeySymbol>` resolves — new path works
- `src.<name>.<KeySymbol> is src.evidence.<name>.<KeySymbol>` is `True` — no duplication

### Circular import check
```
python -c "import src; import src.evidence"
```
Must complete without error.

### Commit
`refactor: move evidence-domain flat modules into src/evidence`

---

## Step 3 — Move deliverables-domain flat modules

### Scope
4 modules into `src/deliverables/`.

### Modules
`output_style`, `pdf_report`, `portfolio`, `reporting`

### Change
1. Move each to `src/deliverables/<name>.py`
2. Leave shims at old flat paths
3. Update `src/deliverables/__init__.py` with named section

### Contract tests required (for each module)
- old flat import resolves
- `src.deliverables.<name>` import resolves
- same object identity through shim

### Circular import check
```
python -c "import src; import src.deliverables"
```

### Commit
`refactor: move deliverables-domain flat modules into src/deliverables`

---

## Step 4a — Move policy-domain flat modules

### Why separate step
`audit_trail` has 12 importers across `src/implement/`, `src/orchestrator.py`,
and 8 test files. Any regression here is high-visibility. Causal isolation in
a dedicated step makes debugging easier.

### Scope
3 modules into `src/policy/`.

### Modules
`audit_trail`, `constraints`, `dry_run`

### Change
1. Move each to `src/policy/<name>.py`
2. Leave shims at old flat paths
3. `src/policy/__init__.py`: add exports for `AuditTrailWriter` and
   `NullAuditTrailWriter` from `audit_trail`; add key types from `constraints`
   and `dry_run` following the existing named-section style

### Contract tests required
For each module:
- old flat import resolves
- `src.policy.<name>` import resolves
- same object identity

Specifically for `audit_trail`:
- `from src.audit_trail import AuditTrailWriter` and
  `from src.policy.audit_trail import AuditTrailWriter` yield the same class
- `from src.audit_trail import NullAuditTrailWriter` and
  `from src.policy.audit_trail import NullAuditTrailWriter` yield the same class

### Circular import check
```
python -c "
import src.policy
import src.implement.implement_loop
import src.implement.document_loop
import src.implement.plan_loop
"
```
Dependency direction must remain `implement → policy` only.
A circular import here (`policy → implement`) would be an architecture failure.

### Commit
`refactor: move policy-domain flat modules into src/policy`

---

## Step 4b — Move workflow and backends flat modules

### Scope
3 modules across two namespace packages.

### Modules

**→ `src/workflows/`**: `run_finalize`, `run_state`
- These are workflow-completion and context-model concerns
- `src/workflows/__init__.py` is a **namespace only** — do NOT add re-exports
- Callers will use: `from src.workflows.run_state import BaseContext`

**→ `src/backends/`**: `backend_options`
- `backend_options.py` currently imports `from .backends import Backend, CallOptions`
  (sibling at `src/` level)
- After move to `src/backends/backend_options.py`, this becomes
  `from . import Backend, CallOptions` — a sibling import within the package
- **Do NOT add `backend_options` to `src/backends/__init__.py`**:
  `__init__.py` runs 17 import statements at init time; adding `backend_options`
  there creates a circular-import risk during package initialization
- Callers will use: `from src.backends.backend_options import build_call_options`

### Change
1. Move each module to its target package
2. Leave shims at all old flat paths
3. `src/workflows/__init__.py`: add a one-line docstring note only
4. `src/backends/__init__.py`: **do not change**

### Contract tests required (for each module)
- old flat import resolves
- new package submodule import resolves
- same object identity through shim

### Circular import check
```
python -c "
import src.workflows
import src.workflows.run_state
import src.workflows.run_finalize
import src.backends
import src.backends.backend_options
"
```
Must complete without error. Verify `backend_options` internal import
`from . import Backend, CallOptions` resolves correctly inside the package.

### Commit
`refactor: move workflow and backends flat modules into domain packages`

---

## Step 5 — Migrate internal callers to canonical package imports

### Scope
Update all production `src/` files to use canonical package paths.
Shims are still present; this step clears callers so Step 6 deletion is safe.

### Canonical import mapping

```
src.agreement_artifacts    → src.evidence.agreement_artifacts
src.artifacts              → src.evidence.artifacts
src.certainty              → src.evidence.certainty
src.comparison             → src.evidence.comparison
src.evaluation_artifacts   → src.evidence.evaluation_artifacts
src.research_logs          → src.evidence.research_logs
src.reproducibility        → src.evidence.reproducibility
src.run_metadata_artifacts → src.evidence.run_metadata_artifacts
src.scorer                 → src.evidence.scorer
src.semantic_eval          → src.evidence.semantic_eval

src.output_style           → src.deliverables.output_style
src.pdf_report             → src.deliverables.pdf_report
src.portfolio              → src.deliverables.portfolio
src.reporting              → src.deliverables.reporting

src.audit_trail            → src.policy.audit_trail
src.constraints            → src.policy.constraints
src.dry_run                → src.policy.dry_run

src.run_finalize           → src.workflows.run_finalize
src.run_state              → src.workflows.run_state

src.backend_options        → src.backends.backend_options
```

### Do NOT touch
- Test files (updated in Step 6 if needed)
- Shim files themselves
- True-core flat modules (cli, config, orchestrator, research_loop, run_paths,
  run_io, explain, doctor, prompts, strategy, provider_instances, runtime_telemetry)

### Required verifications
1. `grep -r "from src\.\(scorer\|artifacts\|certainty\|audit_trail\|output_style\|run_state\|backend_options\)" src/ --include="*.py"` (excluding shims and true-core) — returns nothing
2. Full suite green
3. Full circular import chain:
   ```
   python -c "
   import src.evidence, src.deliverables, src.policy
   import src.workflows, src.backends
   import src.orchestrator, src.research_loop, src.cli
   "
   ```

### Commit
`refactor: migrate internal src imports to canonical domain packages`

---

## Step 6 — Remove compatibility shims; finalize flat layer

### Scope
Delete all 20 shim files. Update any remaining test imports. Finalize docstrings.

### Shims to delete (all in `src/`)
```
agreement_artifacts.py   artifacts.py            certainty.py
comparison.py            evaluation_artifacts.py  research_logs.py
reproducibility.py       run_metadata_artifacts.py scorer.py
semantic_eval.py         output_style.py          pdf_report.py
portfolio.py             reporting.py             audit_trail.py
constraints.py           dry_run.py               run_finalize.py
run_state.py             backend_options.py
```

### Final expected flat layer in `src/`
```
__init__.py           cli.py               config.py
doctor.py             explain.py           orchestrator.py
prompts.py            provider_instances.py  research_loop.py
run_io.py             run_paths.py         runtime_telemetry.py
strategy.py
```
13 files (12 modules + `__init__.py`). Verify with:
```
ls src/*.py | grep -vE "(cli|config|doctor|explain|orchestrator|prompts|provider_instances|research_loop|run_io|run_paths|runtime_telemetry|strategy|__init__)"
```
Must return nothing.

### Change
1. Delete all 20 shim files
2. `grep tests/` for remaining flat-path imports; update to canonical package paths
3. Update `src/evidence/__init__.py`, `src/deliverables/__init__.py`,
   `src/policy/__init__.py` docstrings: replace "MM17 will migrate" with
   "MM17 completed migration of remaining domain modules"

### Required verifications
1. `python -m pytest --collect-only -q` — same count as before step
2. Full suite green (target ≥ 2563)
3. `python -c "import src; import src.orchestrator; import src.cli"` succeeds
4. Flat layer check above returns nothing

### Commit
`refactor: remove flat module shims; finalize domain tree cleanup`

---

## Step 7 — Rename milestone-named test files

### Scope
Rename 9 `test_mm*.py` files using `git mv`. Update docstrings only.

### Renames
```
test_mm13_step4_diagnostics.py              → test_sandbox_backend_diagnostics_truthfulness.py
test_mm14_step1_run_subprocess.py           → test_sandbox_backend_subprocess_contract.py
test_mm14_step2_container_run_subprocess.py → test_container_backend_subprocess.py
test_mm14_step3_executor_delegation.py      → test_sandbox_executor_subprocess_delegation.py
test_mm14_step4_doctor_diagnostics.py       → test_container_backend_readiness_diagnostics.py
test_mm16_step1_iteration_scope.py          → test_iteration_workspace_scope_contract.py
test_mm16_step2_executor_iteration.py       → test_sandbox_executor_iteration_workspace.py
test_mm16_step3_orchestrator_loop.py        → test_orchestrator_iteration_workspace_wiring.py
test_mm16_step4_doctor_explain.py           → test_iteration_workspace_diagnostics.py
```

### Change
For each file: `git mv <old> <new>`, then update the module docstring to remove
the "MM1X Step Y —" prefix while keeping the behavioral description.
Do NOT change any test function, fixture, or assertion.

### Required verifications
1. `python -m pytest --collect-only -q | wc -l` — unchanged
2. Full suite green
3. `ls tests/test_mm*.py` — returns nothing

### Commit
`refactor: rename milestone-named tests to describe behavior`

---

## Acceptance criteria

### Structural
- `src/` flat layer: exactly 13 files (12 true-core modules + `__init__.py`)
- All 20 domain modules live inside bounded-context packages
- No shim files remain after Step 6
- No `test_mm*.py` files remain after Step 7

### Behavioral
- CLI boots: `python -c "from src.cli import main"` succeeds
- No circular imports: full chain check in Step 5 passes
- Collect-only count unchanged through Steps 6 and 7
- No import-time side effects changed in `src/backends/` (backend_options NOT in `__init__.py`)

### Truthfulness
- Three false package docstring claims corrected before any module moves (Step 1)
- Two accurate claims (`implement/`, `execution/`) left untouched
- Package docstrings reflect actual migration state at each commit boundary
- After Step 6: all three corrected packages updated to reflect completion

### Tests
- ≥ 2563 passing at every step
- Contract tests exist for each of the 20 moved modules:
  old path → resolves, new path → resolves, same object identity
- Circular import check passes after every module-movement step

---

## Copilot Prompts

### Step 1 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 1 only.

Context:
- Three package __init__ files contain a false claim: "flat-module imports were removed in MM15 Step 7"
- The flat files still exist: scorer.py, artifacts.py, audit_trail.py, output_style.py, etc.
- This is a truthfulness violation. Fix it before any module moves.
- NOTE: src/implement/__init__.py and src/execution/__init__.py have the same phrase but it IS
  accurate for them — MM15 fully migrated those packages. Do NOT touch those two files.

Rules:
- Documentation only — no module moves, no __init__.py export changes
- One commit for this step only
- Stop after the commit

Files to update:

1. src/evidence/__init__.py
   Current false claim: "flat-module imports were removed in MM15 Step 7"
   Replace with accurate description:
   - List what MM15 migrated: references, provenance, provenance_artifacts, provenance_pipeline
   - Note that scorer, artifacts, certainty, comparison, evaluation_artifacts, research_logs,
     reproducibility, run_metadata_artifacts, semantic_eval, agreement_artifacts
     are evidence-domain modules that remain flat; MM17 will migrate them.

2. src/deliverables/__init__.py
   Same treatment:
   - List what MM15 migrated: pipeline, classes, citation_verification, export_bundle, report_exports
   - Note that output_style, pdf_report, portfolio, reporting remain flat until MM17

3. src/policy/__init__.py
   Same treatment:
   - List what MM15 migrated: hitl, policy_denial, trust, security_runtime,
     tool_capabilities, tool_runtime, sandbox_executor
   - Note that audit_trail, constraints, dry_run remain flat until MM17

Verification:
  python -c "import src; import src.evidence; import src.deliverables; import src.policy"
  Full suite green (no logic changes)

Commit message:
docs: correct false flat-module migration claims in evidence, deliverables, policy

When done, stop and report:

Step completed
- milestone: MM17
- step: 1
- commit:
- tests run:
- result:

What changed
- docstring changes per file

Notes for review
- anything deferred
```

---

### Step 2 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 2 only.

Context:
- MM17 Step 1 complete. Package docstrings are now honest.
- Step 2 moves 10 evidence-domain flat modules into src/evidence/
  using the move+shim pattern from MM15.

Rules:
- TDD: write contract tests alongside the moves
- One commit for this step only
- Stop after the commit

Modules to move into src/evidence/:
  agreement_artifacts, artifacts, certainty, comparison,
  evaluation_artifacts, research_logs, reproducibility,
  run_metadata_artifacts, scorer, semantic_eval

Required changes:
1. Copy each module to src/evidence/<name>.py
2. Leave a shim at each old flat path:
     # src/scorer.py — compatibility shim; canonical: src.evidence.scorer
     from src.evidence.scorer import *  # noqa: F401, F403
3. Update src/evidence/__init__.py: add a named section re-exporting key public
   symbols from each moved module (follow existing section style)
4. Do NOT delete shims

Contract tests required for each module:
  - from src.<name> import <KeySymbol>        → resolves (shim)
  - from src.evidence.<name> import <KeySymbol> → resolves (new path)
  - src.<name>.<KeySymbol> is src.evidence.<name>.<KeySymbol>  →  True

Circular import check (required):
  python -c "import src; import src.evidence"

Commit message:
refactor: move evidence-domain flat modules into src/evidence

When done, stop and report:

Step completed
- milestone: MM17
- step: 2
- commit:
- tests run:
- result:

What changed
- modules moved
- contract tests added
- evidence/__init__.py changes

Notes for review
- any import topology concerns
```

---

### Step 3 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 3 only.

Context:
- MM17 Steps 1 and 2 complete.
- Step 3 moves 4 deliverables-domain flat modules into src/deliverables/.

Rules:
- TDD: write contract tests alongside the moves
- One commit for this step only
- Stop after the commit

Modules to move into src/deliverables/:
  output_style, pdf_report, portfolio, reporting

Required changes:
1. Move each to src/deliverables/<name>.py
2. Leave shims at old flat paths
3. Update src/deliverables/__init__.py with named section (follow existing style)

Contract tests required for each module:
  - old flat import resolves
  - src.deliverables.<name> import resolves
  - same object identity through shim

Circular import check:
  python -c "import src; import src.deliverables"

Commit message:
refactor: move deliverables-domain flat modules into src/deliverables

When done, stop and report:

Step completed
- milestone: MM17
- step: 3
- commit:
- tests run:
- result:

What changed / Notes for review
```

---

### Step 4a Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 4a only.

Context:
- MM17 Steps 1–3 complete.
- Step 4a moves the 3 policy-domain modules. audit_trail is the highest-risk module
  in the entire milestone (12 importers). It gets its own step for causal isolation.

Rules:
- TDD: write contract tests alongside the moves
- One commit for this step only
- Stop after the commit — do not continue to Step 4b automatically

Modules to move into src/policy/:
  audit_trail, constraints, dry_run

Required changes:
1. Move each to src/policy/<name>.py
2. Leave shims at old flat paths
3. src/policy/__init__.py: add AuditTrailWriter and NullAuditTrailWriter from audit_trail,
   and key types from constraints and dry_run, following the existing named-section style

Contract tests required for each module:
  - old flat import resolves
  - src.policy.<name> import resolves
  - same object identity through shim
  Specifically for audit_trail:
  - from src.audit_trail import AuditTrailWriter   and
    from src.policy.audit_trail import AuditTrailWriter  → same class
  - from src.audit_trail import NullAuditTrailWriter  and
    from src.policy.audit_trail import NullAuditTrailWriter → same class

Circular import check (critical):
  python -c "
  import src.policy
  import src.implement.implement_loop
  import src.implement.document_loop
  import src.implement.plan_loop
  "
  Direction must stay: implement → policy. Never policy → implement.

Commit message:
refactor: move policy-domain flat modules into src/policy

When done, stop and report:

Step completed
- milestone: MM17
- step: 4a
- commit:
- tests run:
- result:

What changed / Notes for review
- circular import check result
```

---

### Step 4b Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 4b only.

Context:
- MM17 Steps 1–4a complete.
- Step 4b moves the remaining 3 modules: 2 into workflows, 1 into backends.

Rules:
- TDD: write contract tests alongside the moves
- One commit for this step only
- Stop after the commit

Modules → src/workflows/ (namespace package — no re-exports at __init__ level):
  run_finalize, run_state

  IMPORTANT: src/workflows/__init__.py is a NAMESPACE ONLY.
  Do NOT add re-exports there. Callers use direct submodule paths:
    from src.workflows.run_state import BaseContext
    from src.workflows.run_finalize import finalize_run_artifacts
  Only add a brief docstring note to __init__.py.

Modules → src/backends/ (registration surface — special circular-import risk):
  backend_options

  IMPORTANT: backend_options.py currently imports "from .backends import Backend, CallOptions"
  After the move to src/backends/backend_options.py, this must become:
    from . import Backend, CallOptions
  (sibling import within the package — this is safe)

  Do NOT add backend_options to src/backends/__init__.py.
  Reason: __init__.py runs 17 import statements at initialization; adding backend_options
  there creates a circular-import risk (backend_options imports from the package that is
  still initializing). Callers use the direct path:
    from src.backends.backend_options import build_call_options

Required changes for all 3 modules:
1. Move to target package; fix backend_options internal import as described
2. Leave shims at old flat paths
3. src/workflows/__init__.py: docstring note only
4. src/backends/__init__.py: do not change

Contract tests for each module:
  - old flat import resolves
  - new package submodule import resolves
  - same object identity

Circular import check (required):
  python -c "
  import src.workflows
  import src.workflows.run_state
  import src.workflows.run_finalize
  import src.backends
  import src.backends.backend_options
  "

Commit message:
refactor: move workflow and backends flat modules into domain packages

When done, stop and report:

Step completed
- milestone: MM17
- step: 4b
- commit:
- tests run:
- result:

What changed
- backend_options internal import fix
- contract tests added

Notes for review
- circular import verified
```

---

### Step 5 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 5 only.

Context:
- MM17 Steps 1–4b complete. All 20 modules are in their packages with shims.
- Step 5 updates all production src/ imports to canonical paths so shims can
  be safely deleted in Step 6.

Rules:
- One commit for this step only
- Stop after the commit

Canonical import mapping (replace left → right in src/ production files):
  src.agreement_artifacts    → src.evidence.agreement_artifacts
  src.artifacts              → src.evidence.artifacts
  src.certainty              → src.evidence.certainty
  src.comparison             → src.evidence.comparison
  src.evaluation_artifacts   → src.evidence.evaluation_artifacts
  src.research_logs          → src.evidence.research_logs
  src.reproducibility        → src.evidence.reproducibility
  src.run_metadata_artifacts → src.evidence.run_metadata_artifacts
  src.scorer                 → src.evidence.scorer
  src.semantic_eval          → src.evidence.semantic_eval
  src.output_style           → src.deliverables.output_style
  src.pdf_report             → src.deliverables.pdf_report
  src.portfolio              → src.deliverables.portfolio
  src.reporting              → src.deliverables.reporting
  src.audit_trail            → src.policy.audit_trail
  src.constraints            → src.policy.constraints
  src.dry_run                → src.policy.dry_run
  src.run_finalize           → src.workflows.run_finalize
  src.run_state              → src.workflows.run_state
  src.backend_options        → src.backends.backend_options

Do NOT touch:
  - Test files (shims still cover them; updated in Step 6 if needed)
  - Shim files themselves
  - True-core flat modules: cli, config, orchestrator, research_loop, run_paths,
    run_io, explain, doctor, prompts, strategy, provider_instances, runtime_telemetry

Required verifications:
1. grep src/ (excluding shims + true-core) confirms old flat imports are gone
2. Full suite green
3. Full circular import chain:
   python -c "
   import src.evidence, src.deliverables, src.policy
   import src.workflows, src.backends
   import src.orchestrator, src.research_loop, src.cli
   "

Commit message:
refactor: migrate internal src imports to canonical domain packages

When done, stop and report:

Step completed
- milestone: MM17
- step: 5
- commit:
- tests run:
- result:

What changed
- files updated (list by package)
```

---

### Step 6 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 6 only.

Context:
- MM17 Steps 1–5 complete. All internal src/ imports use canonical paths.
- Step 6 removes all 20 shim files and finalizes the flat layer.

Rules:
- One commit for this step only
- Stop after the commit

Shims to delete (all in src/):
  agreement_artifacts.py  artifacts.py           certainty.py
  comparison.py           evaluation_artifacts.py research_logs.py
  reproducibility.py      run_metadata_artifacts.py scorer.py
  semantic_eval.py        output_style.py         pdf_report.py
  portfolio.py            reporting.py            audit_trail.py
  constraints.py          dry_run.py              run_finalize.py
  run_state.py            backend_options.py

Steps:
1. Delete all 20 shim files
2. grep tests/ for remaining flat-path imports; update to canonical package paths
3. Update src/evidence/__init__.py, src/deliverables/__init__.py, src/policy/__init__.py:
   replace "MM17 will migrate" note with "MM17 completed migration of remaining domain modules"

Final flat layer verification:
  ls src/*.py | grep -vE "(cli|config|doctor|explain|orchestrator|prompts|provider_instances|research_loop|run_io|run_paths|runtime_telemetry|strategy|__init__)"
  Must return nothing.

Required verifications:
1. python -m pytest --collect-only -q → same count as before
2. Full suite green (≥ 2563)
3. python -c "import src; import src.orchestrator; import src.cli"
4. Flat layer check above returns nothing

Commit message:
refactor: remove flat module shims; finalize domain tree cleanup

When done, stop and report:

Step completed
- milestone: MM17
- step: 6
- commit:
- tests run:
- result:

What changed
- shims deleted
- test imports updated
```

---

### Step 7 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 7 only. This is the final MM17 step.

Context:
- MM17 Steps 1–6 complete. Domain tree is fully clean.
- Step 7 renames 9 milestone-named test files to behavior-based names.

Rules:
- One commit for this step only
- This is the final MM17 step

Renames (git mv for each):
  test_mm13_step4_diagnostics.py              → test_sandbox_backend_diagnostics_truthfulness.py
  test_mm14_step1_run_subprocess.py           → test_sandbox_backend_subprocess_contract.py
  test_mm14_step2_container_run_subprocess.py → test_container_backend_subprocess.py
  test_mm14_step3_executor_delegation.py      → test_sandbox_executor_subprocess_delegation.py
  test_mm14_step4_doctor_diagnostics.py       → test_container_backend_readiness_diagnostics.py
  test_mm16_step1_iteration_scope.py          → test_iteration_workspace_scope_contract.py
  test_mm16_step2_executor_iteration.py       → test_sandbox_executor_iteration_workspace.py
  test_mm16_step3_orchestrator_loop.py        → test_orchestrator_iteration_workspace_wiring.py
  test_mm16_step4_doctor_explain.py           → test_iteration_workspace_diagnostics.py

For each file:
1. git mv <old> <new>
2. Update module docstring: remove "MM1X Step Y —" prefix; keep behavioral description
3. Do NOT change any test function, fixture, or assertion

Required verifications:
1. python -m pytest --collect-only -q | wc -l → unchanged
2. Full suite green
3. ls tests/test_mm*.py → no output

Commit message:
refactor: rename milestone-named tests to describe behavior

When done, stop and report:

Step completed
- milestone: MM17
- step: 7 (FINAL)
- commit:
- tests run:
- result:

MM17 complete. Report final test count and confirm all acceptance criteria met.
```
