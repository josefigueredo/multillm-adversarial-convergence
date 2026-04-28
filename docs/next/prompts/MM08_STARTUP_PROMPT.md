# Startup Prompt — MM08 HITL Policy

You are working in:

`/Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence`

## Context

This repository already completed a substantial hardening baseline and is expected to evolve using explicit workflow/state foundations.

### Completed baseline
Assume Milestones 1–5 are complete and available as foundation:
- security/runtime hardening
- explain/doctor workflows
- sandbox executor and capability-based dispatch
- trust semantics and deterministic references
- docs aligned with runtime truth

### Architectural assumption for this milestone
MM08 should build on the workflow architecture direction from the mega plan. HITL must become a **policy-driven workflow layer**, not just a verifier escape hatch.

## Planning docs to use

### Strategic plan
- `doc/megaplan/PLAN.md`

### This milestone brief
- `doc/megaplan/MM08_HITL_POLICY.md`

## What to do now

Start with:

### `doc/megaplan/MM08_HITL_POLICY.md`

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

- preserve inspection-only behavior of `doctor` / `explain`
- do not replace existing HITL flows wholesale
- do not broaden scope into new product modes
- keep review packets, intervention modes, and workflow gates explicit and diagnosable
- keep docs/runtime truth aligned

## First task

Read:
- `doc/megaplan/PLAN.md`
- `doc/megaplan/MM08_HITL_POLICY.md`

Then execute **MM08 Step 1 only**, commit it, and stop for review.
