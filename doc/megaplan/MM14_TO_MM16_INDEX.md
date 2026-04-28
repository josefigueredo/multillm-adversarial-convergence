# Milestone Index — MM14 through MM16

**Approved execution order:** MM14 → MM16 → MM15

All plans reviewed and approved by Codex on 2026-04-27.

These files are the reviewed handoff plans for the next milestone tranche. Keep the execution order strict: **MM14 → MM16 → MM15**.

| File | Milestone | Status | Key correction applied |
|---|---|---|---|
| MM14_CONTAINER_SUBPROCESS_EXECUTION.md | Actual Container Subprocess Execution | pending | argv: list[str] not shell string; ABC first, local_process second, container third |
| MM16_ITERATION_WORKSPACE_ISOLATION.md | Per-Iteration Workspace Isolation | pending (after MM14) | explicit path contract; transient sandbox must follow scope |
| MM15_RESEARCH_OS_FILE_MIGRATION.md | Research OS File Migration | pending (after MM16) | move+shim first; caller cleanup second; shim deletion last (7 steps not 5) |


## Why this order matters

- **MM14** makes the container backend real instead of declarative.
- **MM16** hardens runtime isolation semantics before structural churn.
- **MM15** comes last because file migration is safer after the runtime contracts are settled.

## Quick reference: how to start each milestone

1. Open the milestone file in `doc/megaplan/`.
2. Copy the text inside the `## Copilot Prompt` section's code block.
3. Paste into a fresh Copilot session. Do not mix milestone prompts.
4. After each step: Copilot posts commit hash → you review → you say "approved, proceed to Step N+1".

## Prerequisite chain

```
MM14 complete + approved
    ↓
MM16 complete + approved
    ↓
MM15 complete + approved
```

## Test count baseline at MM14 start: 2469 passing
