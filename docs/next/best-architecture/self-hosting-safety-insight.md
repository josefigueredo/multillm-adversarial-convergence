# Self-Hosting Safety Insight for Adversarial Implementation Workflows

## Context

This note was written as a follow-up clarification after discussing how to automate an adversarial implementation workflow inside this repository. The initial architectural observation was that the repo already supports adversarial role separation well: one backend can build, another can challenge, another can verify or arbitrate. That answer was correct at the pattern level, but it was incomplete for the **actual operating context** the user cared about. The user’s real concern was not whether the adversarial pattern is conceptually valid; it was whether using that pattern **inside this same repository**, against this same repository, to generate the plans and possibly execute the changes, could break the system itself. After re-evaluating that constraint against the codebase, the answer was yes: the current architecture has strong runtime policy controls, artifact tracing, and convergence loops, but it does not yet define a robust self-hosting safety model for autonomous self-modification of the planner/orchestrator repo. In other words, the risk is not lack of adversarial sophistication; the risk is **self-referential mutation**. This document preserves that exact insight so it is not lost later: the correct next step is not merely to add an `implement` mode, but to define a safe separation between the planner/orchestrator repo and the target repo being modified, with patch-only and isolated-apply modes as the default safety boundary. Without this paragraph, the rest of the note could be read too generically and lose the key reason it exists: protecting the repo from unsafe self-application of an otherwise sound adversarial workflow pattern.

## Core insight

The adversarial builder/challenger pattern is valid in this repository's architecture, but it is **not yet safe to use directly against this same repository as the live planning/orchestration codebase**.

In other words:

- the adversarial workflow pattern itself is sound
- but using it to autonomously modify this repo while this repo is also the planner/orchestrator is risky

---

## Why this is risky here

This repository is currently designed primarily to:
- generate plans
- refine documents
- run adversarial research workflows
- emit artifacts, diagnostics, and audit traces

It is **not yet designed as a protected self-editing implementation system**.

### Verified supporting context in this repo

- `src/document_refiner.py` and `src/plan_refiner.py` converge artifacts and write outputs into artifact/output areas
- `src/sandbox_executor.py` and `src/security_runtime.py` provide runtime boundaries, but not a full transactional self-editing planner model
- `src/doctor.py` and `src/explain.py` inspect runs, but they do not provide repository mutation safety guarantees
- `src/strategy.py`, `src/document_strategy.py`, and `src/plan_strategy.py` already implement builder/challenger/verifier/arbitrator flows, but not safe self-hosted repo mutation workflows

So the real problem is not lack of adversarial structure.
The real problem is **self-hosting safety**.

---

## Correct distinction

### Safe use cases
Use this project to:
- generate plans
- critique artifacts
- propose patches
- operate on another target repository
- operate on a disposable clone or worktree

### Unsafe use case (for now)
Do **not** use this project as-is to:
- autonomously edit this same repository while it is also the planner/orchestrator for the change

That is a self-referential mutation problem and can destabilize the system.

---

## Architectural conclusion

The missing capability is not just `implement` mode.
It is a **safe implementation target model**.

Any future implementation workflow should distinguish between:
- the **planner/orchestrator repo**
- the **target repo being edited**

Those should not be assumed to be the same thing.

---

## Recommended safe patterns

### 1. Patch-only mode
Best immediate option.

Flow:
- builder generates patch/diff only
- challenger critiques the patch
- verifier classifies issues
- arbitrator produces revised patch
- human applies the patch manually

Why this is safe:
- no direct self-mutation
- adversarial workflow still works
- easy to integrate with current architecture

### 2. Worktree / clone mode
Best medium-term automation path.

Flow:
- create temporary git worktree or disposable clone
- run builder/challenger loop there
- produce final diff + review artifacts
- merge manually into source-of-truth repo

Why this is safe:
- isolates execution from the planning repo
- supports real edits and tests without corrupting the orchestrator repo

### 3. Target-repo mode
Best long-term architecture.

Future `implement` should explicitly require:
- target repo path
- allowed write roots
- execution mode
- patch export path
- optional apply step

This should never default to editing the planner repo in place.

---

## Recommended execution levels for future `implement`

A safe implementation mode should support explicit levels:

### analyze-only
- no writes
- planning + critique only

### patch-only
- generate diff/patch
- no direct mutation of the source repo

### isolated-apply
- apply changes only in a temporary worktree or clone
- never directly on the planner repo by default

This creates a much safer path toward adversarial implementation automation.

---

## Best architectural recommendation

Do not make the first implementation workflow self-edit this repo directly.

Instead, build:

- `implement --target <path> --patch-only`
- `implement --target <path> --worktree`

with:
- explicit target repo contract
- explicit allowed paths
- patch-only as the default
- review artifacts always emitted
- rollback/reset instructions always available

---

## Final recommendation

The correct architectural rule is:

> use this project to plan and critique freely, but for implementation automation, operate on a detached target or patch-only workflow until a true safe self-editing mode exists.

That is the right safety boundary for this repository's current architecture.
