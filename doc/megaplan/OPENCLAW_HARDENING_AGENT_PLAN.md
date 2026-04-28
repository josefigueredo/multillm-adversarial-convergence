# OpenClaw-Inspired Hardening Plan — Agent Execution Brief

Repository:
`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Mission

Implement the **first major hardening wave** for this research system, inspired by the useful parts of OpenClaw’s architecture:

- stronger execution/security policy modeling
- better operator explainability
- clearer run isolation semantics
- improved reproducibility and trust boundaries

Do **not** turn this repo into a chat gateway or personal assistant system.
Only adapt the patterns that improve a **research orchestration runtime**.

---

## Critical working rules

- Use **TDD**.
- Do **not** build.
- Run tests only.
- Keep changes incremental and well-factored.
- Preserve existing behavior unless the new contract explicitly changes it.
- Prefer explicit config + explicit artifacts over hidden runtime magic.

### Mandatory review cadence

After **each step** below is finished:

1. run the relevant targeted tests
2. make a **separate git commit** for that step using a conventional commit message
3. **STOP**

Do **not** continue automatically to the next step.
The human will review and critique the result before you proceed.

That stop point is mandatory.

---

## Non-goals for this task

Do **not** implement yet:

- Docker/container sandbox backend
- filesystem blocking enforcement
- network restriction enforcement
- policy-denied runtime interception
- trust classification pipeline
- doctor command
- deterministic references generation
- per-iteration isolation
- multi-agent persona routing
- chat/channel concepts

Those are later milestones.

---

## Milestone 1 scope

Implement **only** these four items:

1. Add a first-class `security:` config section
2. Emit `effective_config.json`
3. Add `autoresearch explain config`
4. Add `autoresearch explain resume`

This is the correct first slice because it is:
- high-value
- low-risk
- clarifying
- foundation-setting

---

# Step 1 — Add `security:` config section

## Goal

Introduce a first-class security policy model in `src/config.py`.

## Initial config shape

Keep it simple and explicit:

```yaml
security:
  content_trust: strict
  tool_execution_mode: direct
  allow_host_bash: true
  allow_filesystem_write_outside_output: false
  sandbox:
    mode: off
    scope: run
    filesystem_access: output_only
    network_access: unrestricted
```

## Notes

- This is **policy declaration** in phase 1, not full sandbox enforcement.
- Existing behavior should map to sane defaults.
- Validation must reject invalid enum values.

## Expected implementation

Likely in:
- `src/config.py`
- config loaders / validation helpers

## Required tests first

Update or add tests in:
- `tests/test_config.py`

Cover:
- default values
- parsing valid values
- invalid enum values rejected
- invalid nested sandbox values rejected

## Step-complete action

When Step 1 is complete:
- run targeted config tests
- commit only Step 1 changes
- stop

Suggested commit message:
- `feat: add security config model`

---

# Step 2 — Emit `effective_config.json`

## Goal

Write a normalized machine-readable config artifact after defaults and resolution.

## Purpose

This artifact should answer:
- what config did we actually run with?
- what defaults got applied?
- what style/security/runtime settings are active?

## Output artifact

Write:
- `effective_config.json`

into the run output directory.

## Include at minimum

- full normalized config snapshot
- backend role mapping
- output style
- active style overrides
- security config
- execution config
- reporting config

## Integration

This should be written during the normal run artifact lifecycle.

## Expected implementation

Likely in:
- `src/artifacts.py`
- `src/orchestrator.py`
- possibly a new helper like `src/effective_config.py`

## Required tests first

Add or extend:
- `tests/test_artifacts.py`
- `tests/test_orchestrator.py`

Cover:
- file is written
- content includes normalized security config
- content includes style/reporting/runtime info

## Step-complete action

When Step 2 is complete:
- run targeted artifact/orchestrator tests
- commit only Step 2 changes
- stop

Suggested commit message:
- `feat: add effective config artifact`

---

# Step 3 — Add `autoresearch explain config`

## Goal

Add a CLI explanation command for effective configuration.

## CLI contract

```bash
autoresearch explain config --config <path>
```

## Behavior

Load config and print a human-readable explanation of:
- topic
- goal
- strategy
- backend role mapping
- provider instances
- output style
- active style overrides
- reporting outputs
- security policy
- dry-run relevant paths/artifacts

## Important

This is **explanation**, not execution.

Do **not**:
- create output dirs
- run backends
- instantiate real research execution

## Expected implementation

Likely in:
- `src/cli.py`
- new helper module recommended: `src/explain.py`

## Required tests first

Add tests in:
- `tests/test_cli.py`
- possibly a new `tests/test_explain.py`

Cover:
- explain config returns success
- output includes security policy
- output includes backend role mapping
- output includes output style and artifacts
- no execution happens

## Step-complete action

When Step 3 is complete:
- run targeted CLI/explain tests
- commit only Step 3 changes
- stop

Suggested commit message:
- `feat: add explain config command`

---

# Step 4 — Add `autoresearch explain resume`

## Goal

Add a CLI explanation command for resume state.

## CLI contract

```bash
autoresearch explain resume --output <dir>
```

## Behavior

Inspect an existing output directory and explain:
- whether resume is possible
- how many iterations were found
- whether `results.tsv` exists
- whether `knowledge_base.md` exists
- whether synthesis exists
- whether finalization appears complete
- best score found if recoverable
- what would be reused on resume
- what would be regenerated

## Why

This directly addresses operator confusion around partial runs and resume behavior.

## Expected implementation

Likely in:
- `src/cli.py`
- `src/explain.py`
- existing resume helpers as data sources

## Required tests first

Add tests in:
- `tests/test_cli.py`
- and/or `tests/test_orchestrator.py` / `tests/test_run_state.py`

Cover:
- nonexistent output dir
- partial run dir
- completed run dir
- explanation includes reuse/regeneration summary

## Step-complete action

When Step 4 is complete:
- run targeted resume/explain tests
- commit only Step 4 changes
- stop

Suggested commit message:
- `feat: add explain resume command`

---

# Docs update rules

After each relevant step, update docs only if that step introduces user-visible behavior.

Likely files:
- `README.md`
- `docs/run.md`

Do documentation incrementally, in the same step commit if the behavior is already stable.

---

# Suggested file map

Likely files to touch across the full milestone:

- `src/config.py`
- `src/cli.py`
- `src/artifacts.py`
- `src/orchestrator.py`
- `src/run_paths.py`
- maybe new:
  - `src/explain.py`
  - `src/effective_config.py`

Tests:
- `tests/test_config.py`
- `tests/test_cli.py`
- `tests/test_artifacts.py`
- `tests/test_orchestrator.py`
- maybe `tests/test_explain.py`

Docs:
- `README.md`
- `docs/run.md`

---

# Acceptance criteria for the full milestone

This milestone is complete when:

- `security:` config exists and validates
- `effective_config.json` is written for runs
- `autoresearch explain config --config ...` works
- `autoresearch explain resume --output ...` works
- explain commands do not create output dirs
- tests pass
- docs mention the new explain/effective-config behavior

---

# Recommended execution order

1. Add failing config tests
2. Implement `SecurityConfig`
3. Commit and stop
4. Add failing artifact tests for `effective_config.json`
5. Implement `effective_config.json`
6. Commit and stop
7. Add failing CLI tests for `explain config`
8. Implement `explain config`
9. Commit and stop
10. Add failing CLI tests for `explain resume`
11. Implement `explain resume`
12. Commit and stop

---

# Guidance

Do not be clever.
Be explicit.

This is a **foundation** task.
The goal is to make the system:
- easier to understand
- easier to trust
- easier to operate
- easier to harden later

That is the whole point.
