# Agent Task: Milestone 5 — Stronger Sandbox Isolation

You are working in:

`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Goal

Implement **Milestone 5 — Stronger Sandbox Isolation**.

Milestones 1–4 already gave the project:
- first-class `security:` config
- `effective_config.json`
- `explain` and `doctor` commands
- run-scoped workspace path
- `RuntimeSecurityPolicy`
- `SandboxExecutor`
- executor-owned workspace creation
- write-boundary enforcement
- dispatch-level network enforcement for web tools
- sandboxed backend subprocesses running from the workspace cwd
- audit trail security/runtime events
- trust semantics and deterministic paper references

Milestone 5 must make sandboxing **tighter and more trustworthy**.

That means improving:
- execution environment shaping
- tool capability classification
- dispatch contracts
- operator visibility into what is and is not covered

Do **not** jump to containers yet.

---

## Constraints

### Must follow
- Use **TDD**
- **Never build**
- Run tests only
- Keep changes incremental and well-factored
- Preserve the clean separation between policy resolution and execution
- Prefer explicit contracts over heuristic magic
- Keep diagnostics honest — do not claim stronger guarantees than the code actually provides

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

Do **not** implement in Milestone 5:
- Docker or container sandbox backend
- kernel/firewall-level network controls
- per-iteration sandboxes
- multi-agent sandbox partitions
- trust-model expansion
- doctor feature sprawl
- broad backend rewrites unrelated to sandbox contracts

This milestone is about tightening the **local executor model**, not replacing it.

---

## Architectural intent

### Keep these boundaries clean
- `RuntimeSecurityPolicy` stays **pure**, resolved, immutable, no I/O
- `SandboxExecutor` owns **execution-time shaping and validation**
- tool-capable execution must declare enough intent for policy checks to be meaningful
- `PolicyDeniedError` remains the normalized denial contract
- audit trail remains the system of record for sandbox/security events

### Milestone 5 theme
Milestone 4 made sandboxing **real**.
Milestone 5 must make it **explicit and harder to misuse**.

That means:
- less hidden ambient environment
- less ad hoc tool classification
- clearer execution declarations
- better diagnostics about uncovered paths

---

# What to implement

## Step 1 — Executor-owned environment shaping contract

### Add
Strengthen `SandboxExecutor` so it owns the runtime environment contract for sandboxed execution.

### Responsibilities
- produce a sanitized environment mapping for sandboxed subprocess execution
- make the allowed environment policy explicit and testable
- keep direct mode behavior unchanged

### Suggested shape
Something like:
- `SandboxExecutor.build_environment(base_env: Mapping[str, str] | None = None) -> dict[str, str]`
- optional small helper for allowlist/blocklist resolution

### Minimum contract
- environment shaping happens only for sandboxed execution paths
- environment shaping is deterministic
- ambient environment leakage is reduced intentionally
- the workspace cwd and the environment contract remain separate concerns

### Good first slice
Keep it simple and explicit:
- preserve a small allowlist needed for backend execution
- drop clearly unsafe/noisy variables if appropriate
- document what is preserved vs stripped

Do **not** over-engineer a perfect env sandbox in this step.

### Tests
Add/extend tests covering:
- sandbox executor can build a deterministic environment from a supplied base env
- allowlisted keys are preserved
- stripped keys are removed
- direct-mode paths do not accidentally start using sandbox env shaping

### Deliverable
A real executor-owned environment contract ready to be wired into sandboxed backend calls.

### Commit message suggestion
- `feat: add sandbox executor environment shaping`

### STOP after commit

---

## Step 2 — Tool capability classification

### Add
Introduce a small explicit capability model for tool-capable actions.

### Goal
Stop relying only on scattered hardcoded checks like:
- `WebSearch`
- `WebFetch`
- `Bash`

and move toward a clear contract like:
- writes
- network
- destination type
- host shell

### Suggested shape
Something like:
- `src/tool_capabilities.py`
- `ToolCapability` / helper mapping
- `classify_allowed_tools(...)`

### Minimum capability dimensions
At minimum support:
- `uses_host_shell`
- `uses_network`
- `destination_type` (`web`, `other`, maybe `none`)
- `may_write`

### Important
Keep this intentionally small.
Do **not** build a giant ontology.

### Tests
Add tests covering:
- `Bash` classified as host-shell capable
- `WebSearch` / `WebFetch` classified as networked web tools
- unknown tools handled conservatively and explicitly
- classification output is stable and easy to consume from orchestrator/executor code

### Deliverable
A reusable tool classification layer that replaces ad hoc policy decisions in orchestration code.

### Commit message suggestion
- `feat: add tool capability classification`

### STOP after commit

---

## Step 3 — Tighter dispatch contract for tool-capable execution

### Implement
Route tool-capable execution policy through explicit capability declarations rather than scattered name checks.

### Required behavior
- backend/tool dispatch should validate based on classified capabilities
- network policy should consult the declared destination type
- host-shell policy should consult host-shell capability
- write-sensitive actions should have an explicit path through executor validation

### Important
This step is about reducing policy ambiguity.
The system should know **why** a tool is blocked, not just that its string matched a special case.

### Tests
Add/extend tests proving:
- network-denied tools are blocked because of capability metadata, not raw string checks only
- host-bash denial still works correctly through capability classification
- allowed tools still reach backend execution when policy allows them
- unknown tool behavior is documented and tested (for example: conservative deny vs no capability)

### Deliverable
A cleaner dispatch contract where policy enforcement depends on explicit capability metadata.

### Commit message suggestion
- `feat: enforce sandbox policy through tool capabilities`

### STOP after commit

---

## Step 4 — Diagnostics for coverage and remaining gaps

### Update
Strengthen diagnostics so operators can see what sandbox coverage exists and what still remains uncovered.

### Required updates
At minimum revisit:
- `doctor config`
- optionally `explain config`
- relevant docs in `README.md` and `docs/run.md`

### What diagnostics should surface
Examples:
- sandbox env shaping is active / inactive
- network enforcement is dispatch-level and only applies to classified tools
- unknown/unclassified tool behavior
- remaining non-sandboxed or partially covered execution paths

### Important
Be honest.
If a path is only partially covered, say so.
If unknown tools are conservatively denied, say so.
If they are not covered, say so.

### Tests
Add/update tests for:
- doctor output reflecting env-shaping status
- doctor output reflecting tool classification / dispatch coverage notes
- explain output if you decide to extend it

### Deliverable
Operator-facing diagnostics that make sandbox coverage boundaries visible instead of implicit.

### Commit message suggestion
- `feat: surface sandbox coverage diagnostics`
  or
- `docs: describe stronger sandbox isolation semantics`

### STOP after commit

---

## Step 5 — Final docs alignment and truth-table refresh

### Update
Make the documentation fully reflect the post-M5 sandbox model.

### Must cover
- executor-owned environment shaping
- capability-based dispatch enforcement
- what tool classes are currently recognized
- what remains dispatch-level vs not enforced
- any conservative behavior for unknown tools
- refreshed security truth table

### Required truthfulness
Clearly distinguish:
- runtime-enforced
- dispatch-enforced
- partially covered
- declared-only

Do **not** overclaim container-like guarantees.

### Tests
Only add tests here if docs changes require CLI/output contract updates.
Otherwise keep this step docs-focused.

### Deliverable
Docs and diagnostics aligned with the stronger sandbox-isolation reality.

### Commit message suggestion
- `docs: align sandbox isolation docs with capability-based enforcement`

### STOP after commit

---

# Acceptance criteria

Milestone 5 is complete when:
- sandboxed execution uses an executor-owned environment contract
- tool policy enforcement is driven by explicit capability classification rather than scattered string checks
- dispatch contracts are tighter and harder to bypass accidentally
- diagnostics clearly show sandbox coverage and remaining gaps
- docs reflect the new reality honestly
- tests pass

---

# Design guardrails

## 1. Do not fake container guarantees
If this is still local-process sandboxing, say so.
If env shaping is best-effort, say so.

## 2. Keep direct mode stable
Do not break or silently reshape direct-mode execution.
Sandbox tightening applies to sandboxed paths.

## 3. Prefer explicit capability contracts over name-matching sprawl
If a tool needs policy, it should be classified.
Do not keep scattering new `if tool_name == ...` checks around the codebase.

## 4. Avoid giant abstractions
This repo needs a small, sharp capability model — not a framework.

## 5. Preserve operator truth
`doctor` and `explain` must remain inspection-only.
No hidden side effects.

---

# Suggested files to touch
Likely:
- `src/sandbox_executor.py`
- `src/orchestrator.py`
- `src/tool_capabilities.py` (new)
- `src/doctor.py`
- maybe `src/explain.py`
- `README.md`
- `docs/run.md`

Likely tests:
- `tests/test_sandbox_executor.py`
- `tests/test_orchestrator.py`
- `tests/test_doctor.py`
- maybe `tests/test_explain.py`

---

# Final instruction
Do Step 1 first, with TDD, commit separately, and STOP for review.
Do not continue automatically.
