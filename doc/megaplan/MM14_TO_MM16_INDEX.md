# Milestone Index — MM14 through MM17

**Approved execution order:** MM14 → MM16 → MM15 → MM17

| File | Milestone | Status | Key notes |
|---|---|---|---|
| MM14_CONTAINER_SUBPROCESS_EXECUTION.md | Actual Container Subprocess Execution | ✅ complete | argv contract; ABC first |
| MM16_ITERATION_WORKSPACE_ISOLATION.md | Per-Iteration Workspace Isolation | ✅ complete | explicit path contract |
| MM15_RESEARCH_OS_FILE_MIGRATION.md | Research OS File Migration | ✅ complete | move+shim; 7 steps |
| MM17_FLAT_MODULE_MIGRATION.md | Complete Flat Module Migration | pending | 22 flat modules → domain packages; rename 9 test files |

## Why MM17 follows MM15

MM12/MM15 created and populated domain packages, but ~22 `src/*.py` modules still live flat.
MM17 closes that gap using the same proven move+shim pattern, then renames milestone-named test files to behavior-based names.

## Quick reference: how to start each milestone

1. Open `MM17_FLAT_MODULE_MIGRATION.md` for the Step 1 Copilot Prompt.
2. For Steps 2–7 copy the matching prompt from `MM17-steps.md`.
3. Paste into a fresh Copilot session. Do not mix step prompts.
4. After each step: Copilot posts commit hash → you review → you say "approved, proceed to Step N+1".

## Prerequisite chain

```
MM14 ✅
    ↓
MM16 ✅
    ↓
MM15 ✅
    ↓
MM17 pending
```

## Test count baselines
- MM14 start: 2469 passing
- MM17 start: 2563 passing
