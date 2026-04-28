# Startup Prompt — MM07 Workflow Architecture

You are working in:

`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Context

This repository already completed a substantial hardening baseline.

### Completed baseline
Milestones 1–5 are already done and must be treated as existing foundation:

- explicit `security:` config
- `effective_config.json`
- `explain config` / `explain resume`
- `doctor config` / `doctor output`
- `RuntimeSecurityPolicy`
- `SandboxExecutor`
- executor-owned workspace creation
- workspace cwd for sandboxed subprocesses
- dispatch-level network enforcement
- `ToolCapabilities` registry
- conservative sandbox denial for unclassified tools (`tool_unclassified`)
- sandbox env shaping via `SandboxExecutor.build_environment()`
- `CallOptions.process_env` wired into real backend subprocess execution
- trust classes on claims/citations
- deterministic references for `paper`
- audit trail and docs aligned with runtime truth

## Planning docs to use

### Strategic plan
- `doc/megaplan/PLAN.md`

### This milestone brief
- `doc/megaplan/MM07_WORKFLOW_ARCHITECTURE.md`

## What to do now

Start with:

### `doc/megaplan/MM07_WORKFLOW_ARCHITECTURE.md`

and execute **Step 1 only**.

## Mandatory workflow

For the milestone brief you are executing:

1. follow the brief exactly
2. use **TDD first**
3. do **not build**
4. run tests only
5. make the **smallest correct change**
6. create **one commit for that one step only**
7. **stop after the commit**
8. return a review summary

## Output format after the step

When you stop, report back in this exact structure:

### Step completed
- milestone:
- step:
- commit:
- tests run:
- result:

### What changed
- bullet list of code changes
- bullet list of tests added/updated

### Notes for review
- tradeoffs
- anything uncertain
- anything intentionally deferred

Do **not** continue to the next step automatically.

## Important constraints

- preserve current architecture strengths
- do not rewrite unrelated parts of the repo
- do not collapse modes into a monolithic loop
- keep docs/runtime truth aligned
- prefer explicit contracts over implicit behavior
- workflow state, contracts, and decisions must be added incrementally without destabilizing `run`, `plan`, or `refine`

## First task

Read:
- `doc/megaplan/PLAN.md`
- `doc/megaplan/MM07_WORKFLOW_ARCHITECTURE.md`

Then execute **MM07 Step 1 only**, commit it, and stop for review.
