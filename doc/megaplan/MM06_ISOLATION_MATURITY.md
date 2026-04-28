# Agent Task: Mega Milestone 6 — Isolation Maturity and Sandbox Backend Extensibility

## Goal
Tighten the post-M5 sandbox model without introducing containers yet.

## Why
Milestones 1–5 made sandboxing real. MM6 makes it cleaner, broader, and easier to extend.

## Constraints
- TDD only
- Never build
- Commit each step separately
- Stop after each step for review
- Do not add container runtime yet

## Non-goals
- Docker/container sandbox
- Kernel/firewall enforcement
- Broad backend rewrites
- New product modes

## Step 1 — Extract sandbox backend seam
Add a backend interface under `src/sandbox/backends/` and move current local-process behavior behind it.

### Deliverables
- `src/sandbox/backends/base.py`
- `src/sandbox/backends/local_process.py`
- `SandboxExecutor` delegates workspace/env/validation operations through the local backend

### Tests
- local backend preserves current behavior
- executor behavior unchanged externally

### Commit
`refactor: extract local sandbox backend`

---

## Step 2 — Capability coverage expansion
Expand `ToolCapabilities` coverage and add explicit diagnostics for registry gaps.

### Deliverables
- classify all currently supported tools
- add explicit unknown-tool coverage reporting helpers
- detect unsupported capability combinations

### Tests
- all shipped tools are classified
- unknown tools surfaced clearly
- coverage summaries stable

### Commit
`feat: expand sandbox tool capability coverage`

---

## Step 3 — Environment policy refinement
Refine env shaping into explicit categories: required runtime vars, optional platform vars, denied vars.

### Deliverables
- structured allowlist policy model
- documentation comments explaining why each category exists
- helper(s) to summarize active env strategy

### Tests
- required vars preserved
- optional vars preserved only when configured
- denied vars stripped consistently

### Commit
`feat: refine sandbox environment policy`

---

## Step 4 — Dispatch contract cleanup
Make tool-dispatch validation depend on explicit declared capability metadata only.

### Deliverables
- remove remaining ad hoc capability assumptions
- validate destination classes and write intent through explicit dispatch contract

### Tests
- network/write/host-shell decisions come from capability metadata
- unsupported dispatch combinations fail clearly

### Commit
`feat: tighten sandbox dispatch contracts`

---

## Step 5 — Audit and diagnostics alignment
Update `doctor`, maybe `explain`, and docs to reflect sandbox backend type, capability coverage, and env strategy.

### Deliverables
- doctor coverage summary for sandbox backend type
- env-strategy status surfaced
- docs aligned

### Commit
`docs: align isolation maturity diagnostics`

## Acceptance criteria
- local sandbox is backend-extensible
- capability coverage is broader and diagnosable
- env strategy is explicit and testable
- no container complexity introduced
