# MM14 Plan — Actual Container Subprocess Execution

## Goal
Make the container sandbox backend capable of running real subprocesses through the existing sandbox substrate contract.

## Why this milestone exists
MM13 completed backend selection, truthfulness, and fallback behavior, but the container backend still does not execute subprocesses. MM14 closes that runtime gap.

## Rules
- TDD first
- Never build
- One commit per step
- Stop after each step for review
- Keep local-process behavior intact
- Keep the backend optional

## Important correction to prior draft
Use an **argv-based subprocess contract**, not a shell-string contract.

**Do this:**
- `run_subprocess(argv: tuple[str, ...], *, cwd: Path, env: Mapping[str, str], timeout: int | float | None)`

**Do NOT do this:**
- `run_subprocess(cmd: str, ...)`

Why:
- preserves quoting correctness
- avoids shell ambiguity
- keeps local/container parity honest
- reduces injection and escaping bugs

---

## Step 1 — Add subprocess execution contract to backend interface

### Scope
Update the sandbox backend seam so execution becomes a first-class backend responsibility.

### Change
Add to `src/sandbox/backends/base.py`:
- `run_subprocess(argv, *, cwd, env, timeout) -> tuple[int, str, str]`

Add a matching implementation to `LocalProcessBackend` using `subprocess.run(...)` with:
- `capture_output=True`
- `text=True`
- no shell
- normalized `(returncode, stdout, stderr)` return value

### Tests
Add tests proving:
- backend ABC exposes `run_subprocess`
- `LocalProcessBackend.run_subprocess(...)` executes argv without shell parsing
- stdout/stderr are returned separately
- timeout propagates as a meaningful failure contract you can standardize later

### Commit
`feat: add sandbox backend subprocess execution contract`

---

## Step 2 — Implement container subprocess execution

### Scope
Make `ContainerBackend` run commands through Docker.

### Change
Implement in `src/sandbox/backends/container.py`:
- `run_subprocess(argv, *, cwd, env, timeout)`

Behavior:
- invoke `docker run --rm`
- bind-mount `host_workspace` to `container_workspace`
- set working directory inside container to container-side cwd
- pass env vars explicitly with `--env`
- append image and argv without shell wrapping
- capture stdout/stderr/return code

### Constraints
- all tests must mock `subprocess.run`
- do **not** require live Docker in tests
- no shell string concatenation

### Tests
Add tests proving:
- docker argv is constructed correctly
- mount path mapping uses host→container workspace
- cwd inside container is correct
- env vars become `--env KEY=VALUE`
- backend returns normalized `(rc, stdout, stderr)`
- timeout is passed through correctly

### Commit
`feat: implement container backend subprocess execution`

---

## Step 3 — Expose subprocess execution through SandboxExecutor

### Scope
Make sandboxed callers use the backend execution seam instead of substrate-specific assumptions.

### Change
In `src/sandbox_executor.py` add:
- `run_subprocess(argv, *, cwd=None, env=None, timeout=None)`

Behavior:
- default cwd should be the executor’s authoritative `workspace_dir`
- env should go through `build_environment(...)` unless explicitly provided as already-shaped data
- delegate to active backend

### Tests
Add tests proving:
- executor delegates to backend
- default cwd uses executor workspace
- explicit cwd overrides default
- env shaping still works with both backends

### Commit
`feat: delegate sandbox subprocess execution through executor`

---

## Step 4 — Diagnostics and readiness truth

### Scope
Teach diagnostics to distinguish backend selection from backend readiness.

### Change
Update doctor/explain to show:
- backend selected: `local_process` vs `container`
- container runtime availability: ready vs unavailable
- clear wording that readiness is about runtime presence, not universal guarantees

Recommended wording:
- `container backend configured`
- `docker CLI available` / `docker CLI unavailable`
- avoid overclaiming isolation strength

### Tests
Add tests proving:
- configured container backend + Docker present → ready wording
- configured container backend + Docker absent → warning wording
- local_process unaffected

### Commit
`docs: add container backend readiness diagnostics`

---

## Step 5 — Docs alignment

### Scope
Document the now-real execution path.

### Change
Update docs to state:
- container backend can execute subprocesses through Docker
- argv-based contract, not shell-string behavior
- host workspace vs container workspace distinction
- backend remains optional
- actual runtime requires Docker availability

### Tests / checks
- only docs and any existing text-level tests if present

### Commit
`docs: align container subprocess execution behavior`

---

## Acceptance criteria
- backend execution is a real part of the backend interface
- local and container backends both execute subprocesses through the same contract
- container execution uses argv semantics, not shell-string semantics
- diagnostics distinguish configured vs ready container backend truthfully
- no live Docker required in tests

---

## Copilot Prompt

```text
You are working in:
/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence

Task: execute MM14 Step 1 only.

Context:
- MM13 is complete.
- Container backend exists but does not yet execute subprocesses.
- The next milestone is MM14 Actual Container Subprocess Execution.
- IMPORTANT: use an argv-based subprocess contract, not a shell-string command contract.

Rules:
- TDD first
- never build
- tests only
- one commit for this step only
- stop after the commit
- do not continue to Step 2 automatically

Step 1 goal:
Add subprocess execution as a first-class sandbox backend interface.

Required changes:
1. In src/sandbox/backends/base.py add:
   run_subprocess(argv: tuple[str, ...], *, cwd, env, timeout) -> tuple[int, str, str]
2. Implement the same method in LocalProcessBackend using subprocess.run with:
   - no shell
   - capture_output=True
   - text=True
3. Keep the return contract normalized as:
   (returncode, stdout, stderr)

Tests to add/update:
- backend interface exposes run_subprocess
- LocalProcessBackend executes argv without shell behavior
- stdout/stderr returned separately
- timeout behavior is covered

Commit message:
feat: add sandbox backend subprocess execution contract

When done, stop and report in this structure:

Step completed
- milestone: MM14
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
