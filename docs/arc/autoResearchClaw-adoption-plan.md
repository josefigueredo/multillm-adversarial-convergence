# `~/Code/temp/AutoResearchClaw` (AutoResearchClaw) Adoption Plan for This Repository

This plan is based on verified code review of this repository and the external project at `~/Code/temp/AutoResearchClaw` (AutoResearchClaw).
It focuses on what is realistically useful here, what already exists here, and what should be added without damaging current strengths.

---

## Executive summary

This repository is already stronger than AutoResearchClaw in several operational areas:

- provider-instance architecture
- runtime security policy resolution
- artifact-path centralization
- dry-run / explain / doctor workflows
- manifest / audit / reproducibility discipline
- normalized backend capability modeling

So the goal is **not** to imitate AutoResearchClaw wholesale.

The goal is to import the parts where AutoResearchClaw is genuinely stronger:

1. **workflow-state modeling**
2. **phase contracts**
3. **decision-state architecture**
4. **broader HITL policy model**
5. **execution/validation/repair subsystems**
6. **publication-grade output pipeline**
7. **stronger domain-oriented bounded contexts**

---

## Verified current state of this repository

### What already exists and should be preserved

#### 1. Strong operational architecture
Verified in:
- `src/run_paths.py`
- `src/security_runtime.py`
- `src/artifacts.py`
- `src/doctor.py`
- `src/explain.py`
- `src/provider_instances.py`
- `src/backends/registry.py`

This repo already has:
- centralized run artifact paths
- resolved runtime security policy
- explicit provider-instance contracts
- operator diagnostics and explanation tooling
- effective config snapshots and audit trail discipline

This must remain the foundation.

#### 2. Clear loop extraction
Verified in:
- `src/research_loop.py`
- `src/document_loop.py`
- `src/plan_loop.py`

This repo already extracted loop logic away from the orchestrator.
That is good and should not be undone.

#### 3. Multi-mode product structure
Verified in:
- `src/cli.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/orchestrator.py`

The repo already supports three distinct products:
- `run`
- `refine`
- `plan`

So the right evolution path is a **unified workflow architecture across modes**, not a single monolithic loop.

---

## Verified gaps relative to AutoResearchClaw

### Gap 1 — No explicit workflow-state model
Current reality:
- workflow semantics are distributed across loops and orchestrators
- there is no centralized state/transition model per mode

Impact:
- harder to reason about pauses, rollback, retries, and phase-level status
- harder to build richer HITL policies because workflow state is implicit

### Gap 2 — No contract layer for phases/steps
Current reality:
- artifacts are well-defined globally
- but step-level contracts are not formally declared

Impact:
- harder to answer “what exactly is required before the next step?”
- harder to validate partial runs and reason about correctness by phase

### Gap 3 — Decision semantics are local, not cross-cutting
Current reality:
- `run` uses keep/discard logic
- `refine` and `plan` use valid/stale/deferred critique semantics
- there is no unified decision vocabulary across the product

Impact:
- decisions are hard to compare across modes
- human intervention policy cannot target a shared decision layer cleanly

### Gap 4 — HITL is narrow rather than policy-driven
Current reality:
- HITL centers around verifier deferrals and interactive answers
- pause/resume works, but intervention is not modeled as a broader workflow policy

Impact:
- difficult to support review modes like checkpoint-only, decision-only, co-pilot, or guided approval flows

### Gap 5 — Weak execution/repair subsystem for evidence generation
Current reality:
- there is strong sandbox/security tooling
- but no dedicated execution-validation-diagnosis-repair lifecycle analogous to AutoResearchClaw’s experiment subsystem

Impact:
- generated findings can be critiqued semantically, but there is less explicit architecture for “attempt execution, validate output, diagnose weakness, repair, re-run”

### Gap 6 — Final output pipeline is report-centric, not revision-centric
Current reality:
- strong reporting, provenance, certainty, metrics, and HTML/PDF outputs exist
- but there is less formal distinction between synthesis, revision, publication packaging, and export

Impact:
- great observability, weaker publication-grade flow control

### Gap 7 — Domain modules are thinner than runtime modules
Current reality:
- runtime, tooling, evaluation, and reporting are strong
- domain capabilities such as literature, evidence handling, and deliverable production are less explicitly separated as bounded contexts

Impact:
- architecture feels like a disciplined convergence engine rather than a broader research operating system

---

## Adoption roadmap

---

## Phase 1 — Introduce workflow contracts without destabilizing the codebase

### Goal
Add explicit workflow modeling to `run`, `refine`, and `plan` while preserving current loop/orchestrator structure.

### Deliverables

#### 1. Workflow state definitions per mode
Create modules such as:
- `src/workflows/research_states.py`
- `src/workflows/refine_states.py`
- `src/workflows/plan_states.py`

Define:
- states
- transitions
- allowed terminal states
- pause states
- resume states
- decision states

Suggested starting states:
- `pending`
- `running`
- `paused`
- `needs_human_input`
- `retrying`
- `completed`
- `failed`

#### 2. Phase contracts
Create modules such as:
- `src/workflows/research_contracts.py`
- `src/workflows/refine_contracts.py`
- `src/workflows/plan_contracts.py`

Each contract should define:
- inputs
- outputs
- acceptance criteria
- recoverability
- failure code
- optional human gate

#### 3. Decision vocabulary
Introduce a shared model, for example:
- `accept`
- `reject`
- `refine`
- `pivot`
- `defer_human`
- `retry`

This should be reusable across `run`, `refine`, and `plan`.

### Why this phase first
Because it imports AutoResearchClaw’s best architectural idea — workflow semantics — without forcing a rewrite.

### Code integration targets
- `src/research_loop.py`
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/doctor.py`
- `src/explain.py`

### Expected benefit
- clearer runtime reasoning
- better diagnostics by phase
- easier future HITL improvements
- less orchestration ambiguity

---

## Phase 2 — Expand HITL from verifier deferral into workflow policy

### Goal
Turn human intervention into a configurable product feature, not only a verifier escape hatch.

### Verified current baseline
Already present:
- `src/hitl.py`
- HITL pauses in `document_loop.py` and `plan_loop.py`
- resume handling in `document_refiner.py` and `plan_refiner.py`

### What to add

#### 1. Intervention modes
Suggested config-level modes:
- `full_auto`
- `checkpoint_only`
- `decision_only`
- `co_pilot`
- `step_review`

#### 2. Workflow gates
Examples:
- after hypothesis selection in `run`
- before synthesis in `run`
- after verifier classification in `refine` and `plan`
- before phase 2 artifact expansion in `refine` and `plan`

#### 3. Guidance injection model
Allow human guidance to be stored and injected into the next phase explicitly, instead of only answering deferred questions.

#### 4. Non-interactive review packets
When not interactive, write a structured review packet artifact:
- current state
- open issues
- candidate decision
- required human action
- next resumable command

### Code integration targets
- `src/hitl.py`
- `src/config.py`
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/research_loop.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/orchestrator.py`

### Benefit
This is one of the most valuable imports from AutoResearchClaw because it upgrades the repo from “interactive where needed” to “human collaboration as a policy.”

---

## Phase 3 — Build an execution / validation / repair subsystem

### Goal
Add a dedicated architecture for generated evidence execution and recovery.

### Why this matters here
The repo already has:
- sandbox execution controls
- tool capability contracts
- audit trail discipline

But it lacks a domain-level subsystem that says:
1. generate executable/evaluable step
2. validate it
3. run it
4. diagnose weak/invalid outcomes
5. repair and retry

### Suggested modules
- `src/execution/contracts.py`
- `src/execution/validator.py`
- `src/execution/diagnosis.py`
- `src/execution/repair.py`
- `src/execution/policies.py`

### Initial use cases
- code snippets produced during research
- benchmark verification steps
- reproducibility checks
- evidence-generation procedures
- research claims requiring executable confirmation

### Minimal first contract
For each executable step:
- requested objective
- execution plan
- required tools
- expected outputs
- validation checks
- diagnosis summary on failure
- repair attempts

### Integration targets
- `src/tool_runtime.py`
- `src/sandbox_executor.py`
- `src/security_runtime.py`
- `src/orchestrator.py`
- `src/research_loop.py`
- `src/evaluation_artifacts.py`

### Benefit
This is where AutoResearchClaw’s experiment architecture is genuinely ahead. Importing the pattern would deepen the epistemic quality of your system.

---

## Phase 4 — Split synthesis, revision, and publication packaging

### Goal
Evolve outputs from “strong report generation” to “multi-stage final deliverable production.”

### Verified current baseline
Strong today:
- `src/reporting.py`
- `src/report_exports.py`
- `src/artifacts.py`
- `src/output_style.py`
- `src/reproducibility.py`
- `src/references.py`

### What is missing
There is no strongly modeled distinction between:
- synthesis
- revision
- publication packaging
- export strategy

### What to add

#### 1. Output pipeline stages
A staged post-processing flow such as:
- synthesis draft
- review pass
- revision pass
- packaging/export pass

#### 2. Deliverable classes
Support output classes more explicitly:
- research memo
- technical brief
- paper draft
- PRD package
- plan package

#### 3. Deliverable contract definitions
For each class define:
- required sections
- validation checks
- style constraints
- citation/reference rules
- export targets

#### 4. Revision artifacts
Write artifacts like:
- `review_notes.json`
- `revision_log.json`
- `deliverable_manifest.json`

### Integration targets
- `src/reporting.py`
- `src/report_exports.py`
- `src/output_style.py`
- `src/references.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/orchestrator.py`

### Benefit
This imports one of AutoResearchClaw’s strongest product ideas without discarding your existing artifact/report strengths.

---

## Phase 5 — Strengthen domain-oriented bounded contexts

### Goal
Make the codebase feel more like a research platform and less like a runtime engine with research features attached.

### Suggested bounded contexts

#### 1. Workflow core
Owns:
- state machines
- phase contracts
- decisions
- transitions

#### 2. Provider/runtime platform
Owns:
- backends
- provider instances
- sandbox and security
- tool execution
- capabilities

#### 3. Evidence and provenance
Owns:
- claims
- citations
- evidence links
- contradictions
- trust labels
- certainty tables

#### 4. Evaluation and comparison
Owns:
- scoring
- semantic evaluation
- baseline comparison
- portfolio comparison

#### 5. Deliverables
Owns:
- synthesis
- revision
- output styles
- exports
- reporting bundles

#### 6. Human collaboration
Owns:
- intervention policies
- review packets
- human decisions
- pause/resume collaboration state

### Why this is useful
Your repo already has many of these pieces; they are just not always presented as explicit bounded contexts.
This phase is largely about architectural clarity and future maintainability.

---

## Phase 6 — Optional research-platform expansion

These are useful only if they match product strategy.

### Possible additions inspired by AutoResearchClaw
- literature-specific subsystem
- structured knowledge cards or evidence cards
- domain-specific research templates
- execution resource planning
- deliverable-specific final export workflows

### Important caution
Do not build these because AutoResearchClaw has them.
Build them only if this repository is intentionally expanding from convergence framework into broader research operating system.

---

## Suggested implementation order by ROI

### Highest ROI
1. workflow state model
2. phase contracts
3. shared decision vocabulary
4. broader HITL policy layer

### Medium ROI
5. execution / validation / repair subsystem
6. staged deliverable pipeline

### Longer-term ROI
7. domain bounded-context refactor
8. optional literature/research-platform modules

---

## Concrete first iteration (small, real, safe)

If implementation starts now, the first milestone should be:

### Milestone A — Workflow semantics foundation
- add workflow-state modules
- add phase-contract modules
- wire `doctor` and `explain` to report current workflow phase/state
- add a shared decision enum/model

### Milestone B — HITL policy expansion
- add intervention modes to config
- add explicit gate points for `run`, `refine`, `plan`
- emit structured review packets for non-interactive mode

### Milestone C — Execution/repair pilot
- choose one evidence-generation path in `run`
- add validator + diagnosis + repair loop around it
- emit machine-readable diagnosis artifacts

This sequence gives you the architectural gains from AutoResearchClaw without importing its orchestration bloat.

---

## Final recommendation

The most valuable things to feature in this repository from AutoResearchClaw are:

- **workflow semantics**
- **process contracts**
- **decision-state architecture**
- **broader human collaboration policy**
- **execution/repair lifecycle modeling**
- **staged deliverable production**

Do **not** sacrifice the strengths this repo already has:

- provider-instance design
- security-runtime modeling
- operator diagnostics
- artifact-first evaluation
- path and manifest discipline

The right synthesis is:

**this repo’s operational discipline + AutoResearchClaw’s research-process architecture**.
