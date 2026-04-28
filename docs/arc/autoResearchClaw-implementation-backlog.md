# `~/Code/temp/AutoResearchClaw` (AutoResearchClaw)-Inspired Implementation Backlog

This backlog translates the verified adoption plan into concrete implementation work for this repository.

It is intentionally selective:
- preserve this repo's current strengths
- import only the parts AutoResearchClaw genuinely does better
- avoid copying orchestration bloat

---

## Prioritization model

### ROI scale
- **High** — strong architectural leverage, low-to-moderate disruption
- **Medium** — worthwhile but needs coordination or wider changes
- **Low** — optional or roadmap-dependent

### Risk scale
- **Low** — localized, incremental, easy to validate
- **Medium** — touches multiple modules or runtime semantics
- **High** — broad architectural change with migration risk

---

# Epic 1 — Workflow state model

## Why
Today, workflow semantics are distributed across:
- `src/research_loop.py`
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`

This makes pause/resume, diagnostics, and richer HITL policies harder than they should be.

## Outcome
A centralized state/transition model for each mode.

## ROI
**High**

## Risk
**Medium**

## Tasks

### 1.1 Create workflow state modules
**Files to add**
- `src/workflows/__init__.py`
- `src/workflows/research_states.py`
- `src/workflows/refine_states.py`
- `src/workflows/plan_states.py`

**Task**
Define:
- states
- terminal states
- pause states
- resumable states
- transition rules

**Suggested starting states**
- `pending`
- `running`
- `paused`
- `needs_human_input`
- `retrying`
- `completed`
- `failed`

### 1.2 Add mode-specific workflow phase enums
**Files to add/update**
- `src/workflows/research_states.py`
- `src/workflows/refine_states.py`
- `src/workflows/plan_states.py`

**Task**
Define explicit phases, for example:

#### Research mode
- hypothesis
- execute
- critique
- score
- decide
- persist
- compress
- synthesize

#### Refine mode
- builder
- challenger
- personas
- verifier
- hitl_gate
- arbitrator
- persist
- expansion
- indexing

#### Plan mode
- builder
- challenger
- personas
- verifier
- hitl_gate
- arbitrator
- persist
- expansion
- indexing

### 1.3 Emit workflow state transitions into audit trail
**Files to update**
- `src/audit_trail.py`
- `src/research_loop.py`
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`

**Task**
Write explicit state transition events, not just step events.

### 1.4 Surface current state in diagnostics
**Files to update**
- `src/doctor.py`
- `src/explain.py`

**Task**
Add current phase/state summaries to:
- explain resume
- doctor output

---

# Epic 2 — Phase contracts

## Why
You already have strong artifact discipline globally via `RunPaths` and `artifacts.py`, but not formal contracts for each step/phase.

## Outcome
Every major workflow phase has a machine-readable contract.

## ROI
**High**

## Risk
**Medium**

## Tasks

### 2.1 Introduce contract data model
**Files to add**
- `src/workflows/contracts.py`

**Task**
Define a contract object with:
- phase name
- required inputs
- expected outputs
- acceptance criteria
- error code
- retry policy
- optional human gate flag

### 2.2 Define research contracts
**Files to add**
- `src/workflows/research_contracts.py`

**Task**
Define contracts for:
- hypothesis generation
- execution
- critique
- scoring
- decision
- synthesis

### 2.3 Define refine contracts
**Files to add**
- `src/workflows/refine_contracts.py`

**Task**
Define contracts for:
- builder
- challenger
- personas
- verifier
- arbitrator
- phase 2 artifact generation
- phase 3 indexing

### 2.4 Define plan contracts
**Files to add**
- `src/workflows/plan_contracts.py`

**Task**
Define contracts mirroring plan workflow.

### 2.5 Teach doctor/explain to read phase contracts
**Files to update**
- `src/doctor.py`
- `src/explain.py`

**Task**
Use contract definitions to explain:
- what is missing
- what is resumable
- what phase is incomplete
- what “healthy” means per mode

---

# Epic 3 — Shared decision-state model

## Why
Decision semantics are fragmented:
- `run` uses keep/discard
- `refine` and `plan` use valid/stale/deferred

That works locally, but it prevents a unified product-level workflow model.

## Outcome
A shared decision vocabulary reused across modes.

## ROI
**High**

## Risk
**Low**

## Tasks

### 3.1 Add decision model
**Files to add**
- `src/workflows/decisions.py`

**Task**
Define normalized decisions such as:
- `accept`
- `reject`
- `refine`
- `pivot`
- `retry`
- `defer_human`
- `stale`

### 3.2 Map research-loop outcomes to shared decisions
**Files to update**
- `src/research_loop.py`
- `src/scorer.py`

**Task**
Translate current keep/discard semantics into shared decisions.

### 3.3 Map document/plan verifier outcomes to shared decisions
**Files to update**
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/document_strategy.py`
- `src/plan_strategy.py`

**Task**
Retain current behavior, but normalize internal decision representation.

### 3.4 Emit decision artifacts
**Files to add/update**
- `src/artifacts.py`
- `src/run_metadata_artifacts.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/orchestrator.py`

**Task**
Persist phase decisions in machine-readable form.

---

# Epic 4 — HITL policy modes

## Why
Your current HITL architecture is real, but narrow. It is focused mostly on verifier deferrals and interactive answers.

## Outcome
Human collaboration becomes a configurable product policy.

## ROI
**High**

## Risk
**Medium**

## Tasks

### 4.1 Add HITL policy config
**Files to update**
- `src/config.py`
- relevant config templates under `configs/`

**Task**
Add intervention modes like:
- `full_auto`
- `checkpoint_only`
- `decision_only`
- `co_pilot`
- `step_review`

### 4.2 Add workflow gate definitions
**Files to add**
- `src/workflows/hitl_policy.py`

**Task**
Define where human review is allowed/required per mode.

### 4.3 Expand review checkpoints in `run`
**Files to update**
- `src/research_loop.py`
- `src/orchestrator.py`

**Task**
Add optional gates at:
- post-hypothesis
- post-score / pre-decision
- pre-synthesis

### 4.4 Expand review checkpoints in `refine` and `plan`
**Files to update**
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`

**Task**
Add optional gates at:
- post-verifier
- pre-phase-2 artifact generation
- pre-phase-3 indexing or finalization

### 4.5 Add structured review packets
**Files to add**
- `src/hitl_packets.py`

**Files to update**
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/orchestrator.py`

**Task**
When non-interactive mode pauses, write a packet with:
- current phase/state
- open issues
- candidate decision
- next required action
- resume command

---

# Epic 5 — Execution / validation / diagnosis / repair subsystem

## Why
This is one of the clearest areas where AutoResearchClaw is ahead architecturally.
You already have runtime security and sandboxing, but not a dedicated evidence-execution lifecycle.

## Outcome
Generated executable work can be validated, diagnosed, repaired, and retried as a first-class subsystem.

## ROI
**Medium-High**

## Risk
**High**

## Tasks

### 5.1 Introduce execution subsystem package
**Files to add**
- `src/execution/__init__.py`
- `src/execution/contracts.py`
- `src/execution/validator.py`
- `src/execution/diagnosis.py`
- `src/execution/repair.py`
- `src/execution/policies.py`

### 5.2 Define execution contract
**Files to add/update**
- `src/execution/contracts.py`

**Task**
Each execution attempt should capture:
- objective
- tool requirements
- expected outputs
- validation rules
- retry budget
- diagnosis summary on failure

### 5.3 Integrate sandbox/runtime boundary
**Files to update**
- `src/sandbox_executor.py`
- `src/tool_runtime.py`
- `src/security_runtime.py`

**Task**
Make execution contracts flow through existing sandbox/security boundaries rather than bypassing them.

### 5.4 Pilot one execution-backed use case in `run`
**Files to update**
- `src/orchestrator.py`
- `src/research_loop.py`
- `src/evaluation_artifacts.py`

**Task**
Choose one path, such as:
- evidence verification task
- benchmark reproduction step
- generated code check

Do not generalize before the first path works.

### 5.5 Emit diagnosis/repair artifacts
**Files to update**
- `src/artifacts.py`
- `src/reporting.py`
- `src/report_exports.py`

**Task**
Write artifacts like:
- `execution_diagnosis.json`
- `repair_attempts.json`
- `execution_validation.json`

---

# Epic 6 — Staged deliverable pipeline

## Why
Your outputs are strong, but still more report-centric than publication- or revision-centric.

## Outcome
A multi-stage output pipeline that distinguishes synthesis, review, revision, and export.

## ROI
**Medium**

## Risk
**Medium**

## Tasks

### 6.1 Model deliverable stages
**Files to add**
- `src/deliverables/__init__.py`
- `src/deliverables/contracts.py`
- `src/deliverables/pipeline.py`

### 6.2 Define deliverable classes
**Files to add/update**
- `src/deliverables/contracts.py`
- `src/output_style.py`

**Task**
Support explicit output classes such as:
- research memo
- technical brief
- paper draft
- PRD package
- plan package

### 6.3 Split synthesis from revision/export
**Files to update**
- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/reporting.py`
- `src/report_exports.py`

**Task**
Introduce explicit post-synthesis stages:
- draft
- review
- revision
- export

### 6.4 Add revision artifacts
**Files to update**
- `src/artifacts.py`
- `src/report_exports.py`

**Task**
Emit:
- `review_notes.json`
- `revision_log.json`
- `deliverable_manifest.json`

---

# Epic 7 — Domain-oriented bounded contexts

## Why
The repo is architecturally disciplined, but the most explicit boundaries today are often runtime/platform boundaries rather than research-domain boundaries.

## Outcome
Clearer system decomposition around product capabilities.

## ROI
**Medium**

## Risk
**High**

## Tasks

### 7.1 Define target architecture boundaries
**Files to add**
- `docs/arc/target-architecture.md`

**Task**
Document bounded contexts such as:
- workflow core
- provider/runtime platform
- evidence/provenance
- evaluation/comparison
- deliverables
- human collaboration

### 7.2 Gradually align module ownership
**Files to update over time**
- `src/orchestrator.py`
- `src/artifacts.py`
- `src/reporting.py`
- `src/provenance.py`
- `src/comparison.py`
- `src/semantic_eval.py`
- `src/hitl.py`

**Task**
Move ownership toward explicit bounded contexts rather than one-off utility growth.

---

# Epic 8 — Optional research-platform expansion

## Why
AutoResearchClaw has broader research-domain subsystems, but this only matters if that matches your product direction.

## Outcome
Optional expansion into a broader research operating system.

## ROI
**Low to Medium**

## Risk
**High**

## Candidate tasks
- literature intelligence subsystem
- knowledge-card / evidence-card subsystem
- research templates by deliverable type
- richer benchmark / protocol planning
- publication-targeted export flows

## Recommendation
Do not start here.
Only do this after Epics 1–6 have landed and the product direction clearly demands it.

---

# Recommended rollout order

## Wave 1 — highest leverage, safest
1. Epic 1 — Workflow state model
2. Epic 2 — Phase contracts
3. Epic 3 — Shared decision-state model
4. Epic 4 — HITL policy modes

## Wave 2 — depth and rigor
5. Epic 5 — Execution / validation / diagnosis / repair subsystem
6. Epic 6 — Staged deliverable pipeline

## Wave 3 — structural evolution
7. Epic 7 — Domain-oriented bounded contexts
8. Epic 8 — Optional research-platform expansion

---

# Recommended first milestone

## Milestone A — Workflow Semantics Foundation

### Scope
- add workflow-state modules
- add phase-contract modules
- add shared decision model
- wire doctor/explain to surface current workflow status

### Why
This gives the biggest gain with the least architectural risk.

### Affected files
- `src/research_loop.py`
- `src/document_loop.py`
- `src/plan_loop.py`
- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- `src/doctor.py`
- `src/explain.py`
- new `src/workflows/*`

### Success criteria
- each mode has explicit phases/states
- transitions are machine-readable
- doctor/explain can report incomplete phase status
- no user-facing behavior regression

---

# Recommended second milestone

## Milestone B — HITL Policy Upgrade

### Scope
- intervention modes in config
- workflow gates for all three modes
- review packet artifact for non-interactive pauses

### Success criteria
- interactive and non-interactive modes both produce clear next actions
- human review can be configured by workflow policy, not just verifier deferral

---

# Recommended third milestone

## Milestone C — Execution/Repair Pilot

### Scope
- introduce minimal execution contract
- validate one execution-backed use case in `run`
- emit diagnosis and repair artifacts

### Success criteria
- one execution path can fail safely
- system can explain why it failed
- system can attempt bounded repair rather than generic retry only

---

# Final recommendation

Do not chase breadth first.

The highest-value imports from AutoResearchClaw are architectural semantics, not subsystem count:
- workflow states
- phase contracts
- decisions
- HITL policy
- execution/repair lifecycle
- staged deliverables

The right synthesis remains:

**this repo’s operational discipline + AutoResearchClaw’s research-process architecture**
