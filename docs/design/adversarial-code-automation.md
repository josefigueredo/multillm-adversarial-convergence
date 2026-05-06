# Adversarial Code Automation Insight

## Context

This note was written after reviewing the current architecture of `multillm-adversarial-convergence` and discussing a specific adversarial workflow idea: **Copilot Sonnet performs the task, then Codex reviews and critiques the result**. The important constraint in that conversation was that the desired automation is not abstract research orchestration in the general sense; it is a practical implementation workflow for real work artifacts, potentially including code tasks. During the review, it became clear that this repository already has mature adversarial role separation for **research**, **plan**, and **document refinement** through existing builder/challenger/verifier/arbitrator patterns, provider-instance routing, audit trail support, and HITL pauses. However, it also became clear that those capabilities are currently optimized for producing and converging artifacts, not for acting as a first-class implementation engine that safely performs coding tasks end to end. This document therefore captures a very specific architectural conclusion: the repo already contains most of the adversarial primitives, but the missing capability is a dedicated **implementation-task mode** rather than a reinvention of orchestration itself. That context matters because, without it, this note can be misread as generic advice about multi-agent systems, when in reality it is a recommendation grounded in this repo’s current modes (`run`, `plan`, `refine`), its role mapping semantics, and the practical desire to automate a Copilot-builder / Codex-critic workflow without forcing code execution concerns into the wrong product mode.

## Summary

If the workflow is:

> Copilot Sonnet does the task, then Codex reviews and critiques it

then the architecture should distinguish three different use cases:

1. **Research findings** -> use `run` with `strategy: adversarial`
2. **Plans / specs / PRDs** -> use `plan` or `refine`
3. **Actual code implementation tasks** -> add a dedicated `implement` mode

---

## Verified current state

This repository already has most of the adversarial automation primitives.

### Existing support in `run`
In `src/strategy.py`:
- `AdversarialStrategy.execute_research()` uses `research[0]` as the doer
- `AdversarialStrategy.post_research()` uses `research[1]` as the critic
- `judge` handles adjudication/scoring afterward

This means the repo already supports the shape:
- worker
- critic
- adjudicator

### Existing support in `plan` / `refine`
In:
- `src/document_strategy.py`
- `src/plan_strategy.py`

The roles are already split as:
- `research[0]` = builder
- `research[1]` = challenger
- `utility` = verifier
- `judge` = arbitrator

This is already an adversarial workflow engine.

### Existing Copilot -> Codex example
A working pattern already exists in:
- `configs/research/localstack_alternatives_copilot_codex_technical.yaml`

with:
- `research_coder` -> `copilot-cli` using Sonnet
- `adversary_reasoner` -> `codex-cli`
- `strategy: adversarial`

---

## Architectural conclusion

The repo already automates adversarial workflows well for:
- research
- plans
- documents

The real missing product mode is:
- **implementation-task execution for code changes**

So the gap is **not orchestration architecture**.
The gap is **a first-class `implement` mode**.

---

## Recommended automation path

### Immediate path
Use what already exists:
- `run` for adversarial research workflows
- `plan` / `refine` for adversarial document and task-plan convergence

### Correct long-term path
Add a dedicated mode for code-task execution, for example:
- `src/implement_loop.py`
- `src/implement_strategy.py`
- `src/implement_runner.py`
- CLI entry like `autoresearch implement --config ...`

This mode should reuse the same proven role architecture:
- **Builder** -> Copilot Sonnet implements
- **Challenger** -> Codex critiques
- **Verifier** -> structured classification of critiques
- **Arbitrator / Rewriter** -> accepted critiques become code revisions

---

## Proposed `implement` workflow

1. **Task selection**
   - normalize task input
   - scope repo/files

2. **Builder**
   - Copilot Sonnet implements the task
   - emits patch, touched files, rationale

3. **Challenger**
   - Codex critiques correctness, architecture fit, regressions, edge cases

4. **Verifier**
   - classify critique as valid / stale / deferred / needs human

5. **Arbitrator / Rewriter**
   - apply accepted critiques as patch revisions

6. **Persist**
   - save patch, review outcome, accepted critiques, final artifact, audit trail

---

## Why this fits this repo

This repository already has the necessary foundation:
- loop state objects
- role-based backend assignment
- audit trail
- HITL deferral model
- resume support
- provider-instance config
- sandbox/security boundaries

So the right move is **reuse**, not redesign.

---

## Recommendation

Do **not** force code-task execution into `run`.
Do **not** rewrite the orchestration layer.

Instead:
1. keep using `run` / `plan` / `refine` where they already fit
2. add `implement` as a new first-class mode for adversarial code execution

That is the clean architecture path.
