# Agent Task: Mega Milestone 16 — Per-Iteration Workspace Isolation

**Status:** pending (do after MM14)  
**Approved execution order:** MM14 → MM16 → MM15  
**Prerequisite:** MM14 complete and approved  
**Reviewed by Codex:** 2026-04-27 ✅ (approved; path contract and transient sandbox sharpened)

---

## Review rule

After every committed step: stop, post the commit hash, and wait for human approval before continuing.

## Goal

Each research iteration gets its own isolated subdirectory under `.workspace/` keyed by
iteration number. After MM16, `sandbox.scope: iteration` is an enforced policy option, not
just a vocabulary stub.

---

## Canonical workspace layout (pinned contract)

```
<output_dir>/.workspace/             ← scope=run  (existing behavior)
<output_dir>/.workspace/iter_0001/   ← scope=iteration, iteration 1
<output_dir>/.workspace/iter_0002/   ← scope=iteration, iteration 2
```

Container equivalent:
```
<container_workspace>/               ← scope=run
<container_workspace>/iter_0001/     ← scope=iteration, iteration 1
```

---

## Scope semantics (must be explicit in tests and docs)

| scope | workspace per iteration? | old iteration dirs cleaned? |
|---|---|---|
| `run` | No — shared dir for all iterations | N/A |
| `iteration` | Yes — fresh subdir per iteration | No — persist for audit/debug, not the active cwd |

---

## Step 1 — Config and backend interface: `iteration` scope + path contract

**Config:** add `"iteration"` to `VALID_SANDBOX_SCOPES` in `src/config.py`.

**Base ABC** (`src/sandbox/backends/base.py`):
```python
def prepare_workspace(self, *, iteration: int | None = None) -> Path:
```

**LocalProcessBackend:**
- `iteration=None` → existing behavior
- `iteration=N` → `self._workspace_dir.mkdir(parents=True, exist_ok=True)` then create+return `workspace_dir / f"iter_{N:04d}"`

**ContainerBackend:**
- `iteration=None` → existing behavior
- `iteration=N` → create host subdir `host_workspace / f"iter_{N:04d}"`; return `Path(container_workspace) / f"iter_{N:04d}"`

**Tests first (exact path assertions):**
- `LocalProcessBackend.prepare_workspace(iteration=1)` → creates and returns `workspace/iter_0001/`
- `LocalProcessBackend.prepare_workspace(iteration=99)` → `workspace/iter_0099/`
- `LocalProcessBackend.prepare_workspace()` unchanged
- `ContainerBackend.prepare_workspace(iteration=2)` → returns `/sandbox/workspace/iter_0002`
- `SandboxConfig(scope="iteration")` valid; `scope="call"` still invalid
- All existing `prepare_workspace()` tests pass unchanged

**Commit:** `feat: add iteration scope to sandbox config and workspace provisioning`  
**Stop for review.**

---

## Step 2 — SandboxExecutor and transient sandbox support

Update `SandboxExecutor.prepare_workspace(self, *, iteration: int | None = None)` to forward
`iteration` to backend and update `self._workspace_dir`.

Update `_make_transient_sandbox()` in `src/orchestrator.py`:
- When `scope=iteration` and an active iteration exists, pass `iteration=self.iteration`
- When `scope=run` or before any iteration, pass `iteration=None`

**Tests first:**
- `SandboxExecutor.prepare_workspace(iteration=3)` → delegates `iteration=3`; `workspace_dir` updated to `iter_0003` path
- Write-boundary checks accept paths inside the iteration-scoped workspace
- Transient sandbox with `scope=iteration` respects iteration parameter

**Commit:** `feat: wire iteration workspace through SandboxExecutor and transient sandbox`  
**Stop for review.**

---

## Step 3 — Orchestrator loop wiring + audit events

In `src/orchestrator.py`:

**scope=run (existing behavior — do not change):**
- `_setup_run()` calls `self._sandbox.prepare_workspace()` once

**scope=iteration:**
- `_setup_run()` does NOT call `prepare_workspace()` (skip it)
- Before each iteration: `self._sandbox.prepare_workspace(iteration=self.iteration)`
- Emit audit event: `sandbox_workspace_prepared` with fields `iteration`, `workspace_dir`, `scope`

**Tests first (exact call counts):**
- `scope=run`: `prepare_workspace` called exactly once; `workspace_dir` stable across 2 iterations
- `scope=iteration`: `prepare_workspace()` NOT called in setup; called with `iteration=1` before iter 1, `iteration=2` before iter 2; `workspace_dir` changes between iterations
- Audit trail contains `sandbox_workspace_prepared` events with correct `iteration` and `scope` fields

**Commit:** `feat: apply per-iteration workspace isolation in research loop`  
**Stop for review.**

---

## Step 4 — Doctor and explain updates

Update `doctor_config_text()` in `src/doctor.py`:
- `scope=iteration` → `"workspace isolation: per-iteration (<output>/.workspace/iter_NNNN/)"`
- `scope=run` → `"workspace isolation: per-run (<output>/.workspace/ — shared across iterations)"`

Verify `sandbox.scope` is shown in `explain_config_text()`. If not, add it.

**Tests first (exact wording):** assert the workspace isolation line for each scope value.

**Commit:** `docs: surface per-iteration workspace isolation in doctor and explain`  
**Stop for review.**

---

## Step 5 — Docs alignment

Update `docs/run.md`:
- Document `sandbox.scope: iteration`
- Show the workspace layout table
- Explain the trade-off: per-run is cheaper; per-iteration is cleaner for adversarial runs
  and prevents artifact bleed between iterations

**Commit:** `docs: document per-iteration workspace isolation scope`  
**Stop for review (final MM16 review).**

---

## Copilot Prompt

Paste this verbatim to start MM16 (after MM14 is approved):

```
You are continuing a structured hardening roadmap for this repository.
MM01–MM14 are complete and approved. Start MM16 now.
(MM15 comes after MM16 — do not start MM15.)

## Your working rule — applies to every step

1. Read the files listed under "Context" before writing any code.
2. Write failing tests FIRST. Run them and confirm they fail.
3. Implement the minimum code to make them pass.
4. Run the full test suite: `uv run pytest -x -q`
5. Commit with a conventional prefix (feat:, fix:, docs:, refactor:).
   No Co-authored-by trailers.
6. Post the commit hash and stop. Do NOT proceed to the next step
   until the human explicitly approves.

---

# MM16 — Per-Iteration Workspace Isolation

## Goal

Each research iteration gets its own isolated subdirectory under .workspace/.
After MM16, sandbox.scope: iteration is enforced, not just a vocabulary stub.

## Canonical workspace layout (this is the pinned contract — tests must assert exact paths)

    scope=run:       <output_dir>/.workspace/
    scope=iteration: <output_dir>/.workspace/iter_0001/   (iteration 1)
                     <output_dir>/.workspace/iter_0002/   (iteration 2)

    Container:       <container_workspace>/iter_0001/  etc.

## Scope semantics

    scope=run:       single workspace shared across all iterations; never reset
    scope=iteration: fresh subdir per iteration; old subdirs persist (audit/debug),
                     but the active cwd changes each iteration

## Context — read before writing any code

- src/config.py — SandboxConfig.scope, VALID_SANDBOX_SCOPES
- src/sandbox/backends/base.py — prepare_workspace() signature
- src/sandbox/backends/local_process.py — LocalProcessBackend.prepare_workspace()
- src/sandbox/backends/container.py — ContainerBackend.prepare_workspace()
- src/sandbox_executor.py — SandboxExecutor.prepare_workspace()
- src/orchestrator.py — _setup_run(), _make_transient_sandbox(), iteration loop
- tests/test_sandbox_executor.py — must not break
- tests/test_orchestrator_backend_selection.py — must not break

## Step 1 — Config and backend interface: iteration scope + path contract

In src/config.py: add "iteration" to VALID_SANDBOX_SCOPES = ("run", "iteration").

In src/sandbox/backends/base.py:
    def prepare_workspace(self, *, iteration: int | None = None) -> Path:

In LocalProcessBackend.prepare_workspace():
    iteration=None → existing behavior (unchanged)
    iteration=N    → mkdir workspace_dir; create+return workspace_dir / f"iter_{N:04d}"

In ContainerBackend.prepare_workspace():
    iteration=None → existing behavior (unchanged)
    iteration=N    → create host_workspace / f"iter_{N:04d}"; return Path(container_workspace) / f"iter_{N:04d}"

Tests first (exact path assertions — iter_0001, iter_0099 etc.):
- LocalProcessBackend.prepare_workspace(iteration=1) → workspace/iter_0001/ (created, returned)
- LocalProcessBackend.prepare_workspace(iteration=99) → workspace/iter_0099/
- LocalProcessBackend.prepare_workspace() unchanged
- ContainerBackend.prepare_workspace(iteration=2) → /sandbox/workspace/iter_0002
- SandboxConfig(scope="iteration") valid; scope="call" still raises ValueError
- All existing prepare_workspace() tests pass unchanged

Commit: feat: add iteration scope to sandbox config and workspace provisioning
Stop. Post commit hash. Wait for approval before Step 2.

## Step 2 — SandboxExecutor and transient sandbox support

Update SandboxExecutor.prepare_workspace(self, *, iteration: int | None = None)
to forward iteration to backend and update self._workspace_dir.

Update _make_transient_sandbox() in src/orchestrator.py:
- scope=iteration and active iteration → pass iteration=self.iteration
- scope=run or before any iteration → pass iteration=None

Tests first:
- SandboxExecutor.prepare_workspace(iteration=3) → workspace_dir updated to iter_0003 path
- Write-boundary checks accept paths inside iteration-scoped workspace
- Transient sandbox respects scope/iteration context

Commit: feat: wire iteration workspace through SandboxExecutor and transient sandbox
Stop. Post commit hash. Wait for approval before Step 3.

## Step 3 — Orchestrator loop wiring + audit events

scope=run: _setup_run() calls prepare_workspace() once — existing behavior, do not change.

scope=iteration:
- _setup_run() does NOT call prepare_workspace()
- Before each iteration: self._sandbox.prepare_workspace(iteration=self.iteration)
- Emit audit event "sandbox_workspace_prepared" with fields: iteration, workspace_dir, scope

Tests first (exact call counts and field values):
- scope=run: prepare_workspace called exactly once; workspace_dir stable across 2 iterations
- scope=iteration: prepare_workspace NOT called in setup; called with iteration=1 before iter 1,
  iteration=2 before iter 2; workspace_dir changes between iterations
- Audit trail contains sandbox_workspace_prepared events with correct iteration + scope fields

Commit: feat: apply per-iteration workspace isolation in research loop
Stop. Post commit hash. Wait for approval before Step 4.

## Step 4 — Doctor and explain updates

Update doctor_config_text() in src/doctor.py:
- scope=iteration → "workspace isolation: per-iteration (<output>/.workspace/iter_NNNN/)"
- scope=run → "workspace isolation: per-run (<output>/.workspace/ — shared across iterations)"

Verify sandbox.scope appears in explain_config_text(). Add it if missing.

Tests first: exact wording assertion for each scope value.

Commit: docs: surface per-iteration workspace isolation in doctor and explain
Stop. Post commit hash. Wait for approval before Step 5.

## Step 5 — Docs alignment

Update docs/run.md:
- Document sandbox.scope: iteration with example YAML
- Show the workspace layout table (scope=run vs scope=iteration)
- Explain trade-off: per-run is cheaper; per-iteration prevents artifact bleed in
  adversarial runs

Commit: docs: document per-iteration workspace isolation scope
Stop. Post commit hash. This is the final MM16 step.
Wait for full MM16 review before starting MM15.
```
