# MM17 Step Prompts

Copy the prompt for the current step into a fresh Copilot session.
Do not mix steps. Stop after each commit for review.

---

## Step 2 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 2 only.

Context:
- MM17 Step 1 is complete. Evidence-domain flat modules now live in src/evidence/ with shims at old paths.
- Step 2 moves deliverables-domain flat modules using the same move+shim pattern.

Rules:
- TDD first
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 3 automatically

Step 2 goal:
Move the 4 deliverables-domain flat modules into src/deliverables/ while preserving backward compatibility.

Modules to move into src/deliverables/:
- output_style
- pdf_report
- portfolio
- reporting

Required changes:
1. Move each module into src/deliverables/<name>.py
2. Leave thin compatibility shims at each old flat path
3. Update src/deliverables/__init__.py to include new exports where appropriate
4. Do NOT delete shims yet

Tests to add/update:
- old flat imports still resolve
- new src.deliverables.* imports work
- src.deliverables package exports unchanged
- full suite stays green

Commit message:
refactor: move deliverables-domain flat modules into src/deliverables

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 2
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

---

## Step 3 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 3 only.

Context:
- MM17 Steps 1 and 2 are complete.
- Step 3 migrates 5 modules across two domain packages: policy and workflows.

Rules:
- TDD first
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 4 automatically

Step 3 goal:
Move policy-domain and workflow-domain flat modules into their packages, with shims at old paths.

Modules to move into src/policy/:
- audit_trail
- constraints
- dry_run

Modules to move into src/workflows/:
- run_finalize
- run_state

Required changes:
1. Move each module to its target package
2. Leave shims at old flat paths
3. Update src/policy/__init__.py and src/workflows/__init__.py
4. Do NOT delete shims yet

Tests to add/update:
- old flat imports still resolve for all 5 modules
- new src.policy.* and src.workflows.* imports work
- full suite stays green

Commit message:
refactor: move policy and workflow flat modules into domain packages

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 3
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

---

## Step 4 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 4 only.

Context:
- MM17 Steps 1–3 are complete.
- Step 4 is the last module-movement step: 3 backends-domain flat modules.

Rules:
- TDD first
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 5 automatically

Step 4 goal:
Move the 3 backends-domain flat modules into src/backends/ with shims at old paths.

Modules to move into src/backends/:
- backend_options
- provider_instances
- runtime_telemetry

Required changes:
1. Move each module into src/backends/<name>.py
2. Leave thin compatibility shims at old flat paths
3. Update src/backends/__init__.py
4. Do NOT delete shims yet

Tests to add/update:
- old flat imports still resolve for all 3 modules
- new src.backends.* imports work
- full suite stays green

Commit message:
refactor: move backends-domain flat modules into src/backends

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 4
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

---

## Step 5 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 5 only.

Context:
- MM17 Steps 1–4 are complete. All 22 domain modules now have canonical package locations and flat shims.
- Step 5 updates all internal production src/ imports to use canonical package paths.
- Tests still use shims — leave them for Step 6.

Rules:
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 6 automatically

Step 5 goal:
Update all repo-internal src/ imports to prefer canonical domain package paths.

Target import changes — replace flat with package:
- src.scorer → src.evidence.scorer
- src.artifacts → src.evidence.artifacts
- src.certainty → src.evidence.certainty
- src.comparison → src.evidence.comparison
- src.evaluation_artifacts → src.evidence.evaluation_artifacts
- src.research_logs → src.evidence.research_logs
- src.reproducibility → src.evidence.reproducibility
- src.run_metadata_artifacts → src.evidence.run_metadata_artifacts
- src.semantic_eval → src.evidence.semantic_eval
- src.agreement_artifacts → src.evidence.agreement_artifacts
- src.output_style → src.deliverables.output_style
- src.pdf_report → src.deliverables.pdf_report
- src.portfolio → src.deliverables.portfolio
- src.reporting → src.deliverables.reporting
- src.audit_trail → src.policy.audit_trail
- src.constraints → src.policy.constraints
- src.dry_run → src.policy.dry_run
- src.run_finalize → src.workflows.run_finalize
- src.run_state → src.workflows.run_state
- src.backend_options → src.backends.backend_options
- src.provider_instances → src.backends.provider_instances
- src.runtime_telemetry → src.backends.runtime_telemetry

Do NOT touch:
- Test files (shims still cover them; cleaned in Step 6)
- Shim files themselves
- True-core flat modules: cli, config, orchestrator, research_loop, run_paths, run_io, explain, doctor, prompts, strategy

Verification:
- After changes: grep confirms none of the old flat imports remain in src/ production files (excluding shims)
- Full suite stays green

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
- bullet list of files updated
- summary of import paths changed

Notes for review
- tradeoffs
- anything deferred
```

---

## Step 6 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 6 only.

Context:
- MM17 Steps 1–5 complete. Canonical package imports are in place in production src/ files.
- Step 6 removes all shims created in Steps 1–4 and updates any remaining test imports.

Rules:
- never build
- one commit for this step only
- stop after the commit
- do not continue to Step 7 automatically

Step 6 goal:
Remove all flat compatibility shims. Update any test files still importing via old flat paths.

Shim files to delete (all in src/):
agreement_artifacts.py, artifacts.py, certainty.py, comparison.py,
evaluation_artifacts.py, research_logs.py, reproducibility.py,
run_metadata_artifacts.py, scorer.py, semantic_eval.py,
output_style.py, pdf_report.py, portfolio.py, reporting.py,
audit_trail.py, constraints.py, dry_run.py,
run_finalize.py, run_state.py,
backend_options.py, provider_instances.py, runtime_telemetry.py

Steps:
1. Delete all shim files listed above
2. grep tests/ for any imports that used old flat paths; update those to canonical package paths
3. Verify the final src/ flat layer contains only:
   __init__.py, cli.py, config.py, doctor.py, explain.py,
   orchestrator.py, prompts.py, research_loop.py, run_io.py,
   run_paths.py, strategy.py
4. Full suite must be green without shims

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
- tradeoffs
- anything deferred
```

---

## Step 7 Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM17 Step 7 only.

Context:
- MM17 Steps 1–6 complete. Domain tree is fully clean.
- Step 7 renames the 9 milestone-named test files to behavior-based names.
  These names encode implementation history, not behavior, and will confuse future contributors.

Rules:
- never build
- one commit for this step only
- stop after this step — MM17 is complete

Step 7 goal:
Rename milestone-named test files to describe what they test, not when they were written.

Renames (use git mv for each):
- test_mm13_step4_diagnostics.py          → test_sandbox_backend_diagnostics_truthfulness.py
- test_mm14_step1_run_subprocess.py       → test_sandbox_backend_subprocess_contract.py
- test_mm14_step2_container_run_subprocess.py → test_container_backend_subprocess.py
- test_mm14_step3_executor_delegation.py  → test_sandbox_executor_subprocess_delegation.py
- test_mm14_step4_doctor_diagnostics.py   → test_container_backend_readiness_diagnostics.py
- test_mm16_step1_iteration_scope.py      → test_iteration_workspace_scope_contract.py
- test_mm16_step2_executor_iteration.py   → test_sandbox_executor_iteration_workspace.py
- test_mm16_step3_orchestrator_loop.py    → test_orchestrator_iteration_workspace_wiring.py
- test_mm16_step4_doctor_explain.py       → test_iteration_workspace_diagnostics.py

For each file:
1. git mv <old_name> <new_name>
2. Update the module-level docstring to remove the "MM1X Step Y —" prefix; keep the behavioral description

Do NOT change any test logic, fixtures, or assertions.

Verification:
- pytest collects all renamed files
- test count unchanged (≥ 2563)
- no test_mm*.py files remain in tests/

Commit message:
refactor: rename milestone-named tests to describe behavior

When done, stop and report in this structure:

Step completed
- milestone: MM17
- step: 7 (final)
- commit:
- tests run:
- result:

What changed
- list of renames

Notes for review
- tradeoffs
- anything deferred

MM17 is complete after this step.
```
