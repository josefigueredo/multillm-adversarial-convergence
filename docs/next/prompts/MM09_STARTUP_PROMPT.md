# Startup Prompt — MM09 Implement Mode

You are working in:

`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Context

This repository already supports adversarial role separation well for research, plans, and document refinement.
The next product expansion is a dedicated **implement mode** for code work.

### Critical safety insight
This repository must **not** default to autonomously self-editing itself in place.
Implementation automation must distinguish:
- the planner/orchestrator repo
- the target repo being modified

Safe defaults must be:
- `analyze_only`
- `patch_only`
- `isolated_apply`

Patch-only should be the default.

## Planning docs to use

### Strategic plan
- `doc/megaplan/PLAN.md`

### This milestone brief
- `doc/megaplan/MM09_IMPLEMENT_MODE.md`

### Supporting architecture context
- `docs/next/adversarial-code/automation-insight.md`
- `docs/next/best-architecture/self-hosting-safety-insight.md`

## What to do now

Start with:

### `doc/megaplan/MM09_IMPLEMENT_MODE.md`

and execute **Step 1 only**.

## Mandatory workflow

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

Do **not** continue automatically.

## Important constraints

- do not force implementation automation into `run`
- do not self-edit this repo by default
- patch-only must be the default execution level
- target repo separation must be explicit in the design
- preserve audit/artifact/diagnostic discipline from the existing repo foundations
- keep docs/runtime truth aligned

## First task

Read:
- `doc/megaplan/PLAN.md`
- `doc/megaplan/MM09_IMPLEMENT_MODE.md`
- `docs/next/adversarial-code/automation-insight.md`
- `docs/next/best-architecture/self-hosting-safety-insight.md`

Then execute **MM09 Step 1 only**, commit it, and stop for review.
