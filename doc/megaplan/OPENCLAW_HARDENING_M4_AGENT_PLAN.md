# Agent Task: Milestone 4 — Sandbox Runtime Enforcement

You are working in:

`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Goal

Implement **Milestone 4 — Sandbox Runtime Enforcement**.

Milestones 1–3 already gave the project:
- first-class `security:` config
- `effective_config.json`
- `explain` and `doctor` commands
- run-scoped workspace path
- partial enforcement (`allow_host_bash`, `guard_path_write`)
- audit trail security events
- trust semantics and deterministic paper references

Milestone 4 must make sandbox intent **operationally real** for tool-capable execution.

That means moving from:
- policy declaration
- diagnostics
- partial explicit guards

to:
- real execution through a sandbox executor boundary
- real workspace-bounded execution
- real dispatch-level network policy behavior

Do **not** turn this into Docker/container orchestration yet.

---

## Constraints

### Must follow
- Use **TDD**
- **Never build**
- Run tests only
- Keep changes incremental and well-factored
- Separate policy resolution from runtime execution
- Preserve existing behavior unless the new contract explicitly changes it
- Prefer explicit enforcement and explicit denial messages over hidden magic

### Required workflow
For **every step** below:
1. write failing tests first
2. implement the smallest correct slice
3. run targeted tests
4. commit that step separately
5. **STOP and wait for review**

Do **not** batch multiple steps into one commit.
Do **not** continue automatically after a step.

---

## Non-goals

Do **not** implement in Milestone 4:
- Docker or container sandbox runtime
- per-iteration sandboxes
- kernel/firewall-level network enforcement
- multi-agent sandbox partitions
- trust-model expansion
- doctor feature sprawl
- broad unrelated refactors

This milestone is about making `sandboxed` execution **real enough** through a lightweight local executor.

---

## Architectural intent

### Keep these boundaries clean
- `RuntimeSecurityPolicy` stays **pure**, resolved, immutable, no I/O
- `SandboxExecutor` handles **actual execution behavior**
- `PolicyDeniedError` remains the normalized denial contract
- audit trail stays the system of record for security/runtime events

Do **not** move execution behavior into `RuntimeSecurityPolicy`.
Do **not** let `SandboxExecutor` invent new policy semantics outside `SecurityConfig`.

---

# What to implement

## Step 1 — `SandboxExecutor` abstraction

### Add
A new module:
- `src/sandbox_executor.py`

### Responsibilities
- own the run-scoped execution boundary for tool-capable work
- operate from `paths.workspace_dir`
- consume a `RuntimeSecurityPolicy`
- expose explicit validation + execution entrypoints

### Suggested shape
Something like:
- `SandboxExecutor(policy, workspace_dir)`
- `prepare_workspace()`
- `validate_tool_request(...)`
- `execute(...)`

Do not over-design the API. Keep it small and obvious.

### Minimum contract
- workspace/cwd is explicit
- executor has access to allowed write roots
- executor exposes whether network mode is:
  - `unrestricted`
  - `web_only`
  - `none`

### Tests
Add `tests/test_sandbox_executor.py` covering:
- executor can be constructed from a resolved policy
- workspace dir is the execution root
- allowed write roots come from the runtime policy
- no filesystem side effects are created just by construction

### Deliverable
A concrete executor abstraction ready to be wired, but not yet fully integrated.

### Commit message suggestion
- `feat: add sandbox executor abstraction`

### STOP after commit

---

## Step 2 — Filesystem-bounded execution semantics

### Implement
Use `SandboxExecutor` to make filesystem boundaries operationally real.

### Required behavior
- when `sandbox.filesystem_access == output_only`:
  - writes must stay within `output_dir`
- when `sandbox.filesystem_access == workspace_only`:
  - writes must stay within `output_dir/.workspace`
- when `allow_filesystem_write_outside_output == true`:
  - broad writes are permitted

### Important
Do **not** rely only on ad hoc guard calls.
The executor should own the write-boundary validation for the paths it manages.

### Tests
Extend `tests/test_sandbox_executor.py` (or add focused tests) covering:
- workspace-only denies output-dir-root writes
- output-only denies outside writes
- workspace-only allows workspace writes
- broad-write flag allows outside paths
- denied writes raise `PolicyDeniedError` with:
  - `reason_code=write_outside_allowed_roots`
  - correct `policy_field`
  - correct `allowed_boundary`

### Deliverable
Actual filesystem-boundary enforcement inside the executor.

### Commit message suggestion
- `feat: enforce sandbox write boundaries`

### STOP after commit

---

## Step 3 — Dispatch-level network policy behavior

### Implement
Make `sandbox.network_access` operationally meaningful at executor-dispatch level.

### Meaning for Milestone 4
This is **not** kernel-level firewalling.
It is explicit execution-policy enforcement.

### Required behavior
- `unrestricted` → allow all executor-declared networked actions
- `web_only` → allow only requests/tools declared as `destination_type="web"`
- `none` → deny executor-declared networked actions

### Important
Be honest in docs/comments that this is **dispatch-level enforcement**, not OS-level network isolation.

### Suggested API support
- execution requests declare `destination_type` when network is involved
- executor validates it before execution

### Tests
Add coverage for:
- `none` denies networked actions with `PolicyDeniedError(reason_code="network_access_disallowed")`
- `web_only` allows `destination_type="web"`
- `web_only` denies `destination_type="other"`
- `unrestricted` allows both

### Deliverable
`RuntimeSecurityPolicy.network_access` becomes operationally meaningful in real execution flow.

### Commit message suggestion
- `feat: enforce sandbox network policy at dispatch level`

### STOP after commit

---

## Step 4 — Route real tool-capable execution through `SandboxExecutor`

### Implement
Wire actual tool-capable execution paths through the new executor.

### Critical rule
Only route **real** tool-capable paths.
Do not refactor unrelated code just for aesthetics.

### Existing reality to build on
Current enforcement already exists in `AutoResearcher` for:
- host bash denial in `_call_with(...)`
- explicit path guard via `guard_path_write(...)`

Now the goal is to move from:
- isolated checks

to:
- execution through executor boundary where appropriate

### Required behavior
- denied requests must fail **before** underlying execution happens
- allowed requests must use the executor workspace
- existing explicit denial semantics must remain stable

### Tests
Add/extend tests proving:
- denied tool-capable execution does not invoke underlying backend/tool path
- allowed execution uses workspace cwd
- bash denial still works through the integrated path
- network denial works through the integrated path
- write denial works through the integrated path

### Deliverable
A real execution path now flows through `SandboxExecutor` instead of only scattered guards.

### Commit message suggestion
- `feat: route tool execution through sandbox executor`

### STOP after commit

---

## Step 5 — Audit trail, doctor, explain, and docs update

### Update audit trail if needed
If Step 4 introduces new meaningful runtime facts, emit them.
Possible event enrichments:
- executor mode / workspace cwd
- network policy applied at execution time
- denied network action details

Do **not** invent noisy events without clear value.

### Update operator-facing tools
Update as needed:
- `doctor config`
- maybe `explain config`
- docs in `README.md` and `docs/run.md`

### Required doc truthfulness
Clearly distinguish:
- enforced at executor-dispatch level
- still declared-only
- not OS-level / not container-level

### Update truth table
After Milestone 4, at minimum revisit status for:
- `sandbox.network_access`
- `tool_execution_mode: sandboxed`

If they become only **partially enforced**, say so explicitly.
Do not overclaim.

### Tests
Add/update tests where needed for:
- doctor/explain output reflecting new enforcement reality
- docs-backed command examples if you already use CLI contract tests

### Deliverable
Runtime truth, diagnostics, and docs all aligned again.

### Commit message suggestion
- `docs: describe sandbox executor enforcement semantics`
  or
- `feat: surface sandbox executor enforcement in diagnostics`

### STOP after commit

---

# Acceptance criteria

Milestone 4 is complete when:
- tool-capable execution has a real `SandboxExecutor` boundary
- workspace-bounded execution is operationally real
- filesystem enforcement is executor-owned, not only manual call-site discipline
- `sandbox.network_access` has real dispatch-level behavior
- denials still use stable `PolicyDeniedError` semantics
- audit / doctor / docs reflect the new enforcement truth honestly

---

# Design guardrails

## 1. Do not fake stronger guarantees than you have
If network enforcement is only dispatch-level, say that.
If sandboxing is still local-process-level, say that.

## 2. Do not break Milestone 3 operator semantics
`doctor` and `explain` must remain inspection-only.
No directories, no backends, no execution.

## 3. Do not collapse concerns
- policy resolution ≠ execution
- execution ≠ diagnostics
- diagnostics ≠ docs

## 4. Prefer small, reviewable steps
This milestone is exactly the kind of work that turns into mud if you batch too much.
Don’t.

---

# Suggested files to touch
Likely:
- `src/sandbox_executor.py` (new)
- `src/orchestrator.py`
- `src/security_runtime.py`
- `src/policy_denial.py` (only if needed for new reason usage)
- `src/doctor.py`
- `src/cli.py` (only if diagnostics output changes)
- `README.md`
- `docs/run.md`

Likely tests:
- `tests/test_sandbox_executor.py` (new)
- `tests/test_orchestrator.py`
- `tests/test_doctor.py`
- possibly `tests/test_cli.py`

---

# Final instruction
Do Step 1 first, with TDD, commit separately, and STOP for review.
Do not continue automatically.
