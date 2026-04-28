# What `~/Code/temp/AutoResearchClaw` (AutoResearchClaw) Does Better — Verified Summary

This summary compares the external project at `~/Code/temp/AutoResearchClaw` (AutoResearchClaw) against this repository (`multillm-adversarial-convergence`) and captures only ideas that appear genuinely stronger or more mature in AutoResearchClaw after reviewing both codebases.

## Bottom line

AutoResearchClaw is not operationally cleaner than this repo. This repo is stronger in provider contracts, security policy resolution, artifact discipline, and operator tooling. But AutoResearchClaw is better in a different dimension: it models the **research workflow itself** more explicitly.

The biggest reusable advantages from AutoResearchClaw are:

1. **Explicit stage-machine workflow**
2. **Stage-by-stage contracts**
3. **Formal research decision states**
4. **Richer human-in-the-loop architecture**
5. **Stronger domain decomposition around research work**
6. **Execution / validation / repair as a dedicated subsystem**
7. **Better final deliverable / publication pipeline**

---

## 1. Explicit stage-machine workflow

AutoResearchClaw has a first-class workflow backbone in:

- `~/Code/temp/AutoResearchClaw/researchclaw/pipeline/stages.py`
- `~/Code/temp/AutoResearchClaw/researchclaw/pipeline/contracts.py`

Why this is stronger:

- the system is modeled as a **23-stage state machine**
- stage transitions, rollback targets, gate stages, and retries are explicit
- workflow semantics are separated from implementation details

Why this matters here:

- this repo has clear loops (`research_loop.py`, `document_loop.py`, `plan_loop.py`) and phase-oriented orchestrators (`orchestrator.py`, `document_refiner.py`, `plan_refiner.py`)
- but workflow semantics are still spread across loops, conditionals, and orchestrator logic rather than being declared centrally as a reusable model

What is worth borrowing:

- explicit workflow/state definitions for `run`, `refine`, and `plan`
- formal transition maps instead of implicit phase sequencing
- central rollback / resume / gate policy definitions

---

## 2. Stage-by-stage contracts

`~/Code/temp/AutoResearchClaw` (AutoResearchClaw)’s `~/Code/temp/AutoResearchClaw/researchclaw/pipeline/contracts.py` is one of its strongest ideas.

Why this is stronger:

- each stage declares:
  - required inputs
  - expected outputs
  - definition of done
  - error code
  - retry allowance
- artifacts are attached to workflow meaning, not just file names

Why this matters here:

- this repo has excellent artifact discipline globally (`RunPaths`, `artifacts.py`, `doctor.py`), but it does **not** yet define formal process contracts for each workflow step
- `run`, `refine`, and `plan` are operationally clear, but acceptance criteria live in code behavior and prompts rather than a durable contract layer

What is worth borrowing:

- contract objects for each major step or phase
- mode-specific acceptance rules
- retry / recovery policy by phase
- explicit machine-readable definitions of “done” for convergence steps and report-generation steps

---

## 3. Formal research decision states

AutoResearchClaw has a stronger notion of **research progression as decision-making**:

- hypothesis generation
- experiment design
- execution
- analysis
- proceed / refine / pivot decisions

Why this is stronger:

- it treats research as a system of epistemic checkpoints, not just generation and scoring
- it has a clearer answer to “what happens next if the evidence is weak?”

Why this matters here:

- this repo has keep/discard semantics in `research_loop.py`
- `refine` and `plan` have convergence semantics with valid/stale/deferred critiques
- but there is no shared, explicit decision-state model spanning the product

What is worth borrowing:

- formal decision states like `proceed`, `refine`, `pivot`, `reject`, `needs-human-input`
- a cross-mode decision vocabulary
- durable decision artifacts instead of only emergent behavior from loops

---

## 4. Richer human-in-the-loop architecture

AutoResearchClaw has a more ambitious HITL runtime:

- intervention modes
- pause-before / pause-after semantics
- stage gates
- guidance injection
- claim verification hooks
- collaboration-oriented session concepts

Why this is stronger:

- human collaboration is treated as a first-class runtime concern
- the intervention model is attached to meaningful process moments, not just deferrals

Why this matters here:

- this repo already has meaningful HITL capability in `hitl.py`, `document_loop.py`, `plan_loop.py`, `document_refiner.py`, and `plan_refiner.py`
- however, it is mostly centered on deferred critique resolution, interactive questions, and pause/resume around verifier uncertainty
- AutoResearchClaw’s model is broader and more policy-driven

What is worth borrowing:

- configurable intervention modes
- explicit gate checkpoints for key workflow transitions
- richer guidance injection before or after a workflow step
- stage-aware human oversight beyond verifier deferrals

---

## 5. Stronger domain decomposition around research work

AutoResearchClaw is more product-shaped in its subsystem split. It has dedicated packages for:

- literature
- experiment
- templates
- memory
- overleaf
- assessor
- hitl
- skills
- server

Why this is stronger:

- it decomposes around research capabilities, not only runtime concerns
- the architecture looks like a research platform, not just a convergence engine

Why this matters here:

- this repo is architecturally disciplined but still centered around:
  - orchestration
  - provider/backend routing
  - evaluation layers
  - reporting
  - convergence loops
- that is excellent engine architecture, but the domain model is thinner

What is worth borrowing:

- stronger domain-focused modules for literature, evidence assessment, deliverable generation, and research workflows
- clearer bounded contexts around “what the system is helping produce,” not only “how it runs”

---

## 6. Execution / validation / repair as a real subsystem

AutoResearchClaw treats experiment execution as its own architecture:

- execution backend selection
- sandbox / docker / ssh / colab modes
- resource planning
- experiment diagnosis
- repair loops
- validator layer

Why this is stronger:

- execution is not just another step in the loop
- it has explicit validation and recovery semantics

Why this matters here:

- this repo has strong runtime security, sandboxing, and tool-execution governance
- but it does not yet model a dedicated “execution + diagnosis + repair” subsystem for evidence generation or experimental verification

What is worth borrowing:

- explicit execution plans
- validation layers over generated outputs
- diagnosis artifacts when an execution attempt is weak or invalid
- repair/refinement cycles that are separate from generic critique loops

---

## 7. Better final deliverable / publication pipeline

AutoResearchClaw is more mature in its “last mile” output model:

- outline
- draft
- review
- revision
- export/publish
- citation verification
- template and Overleaf-oriented thinking

Why this is stronger:

- it separates synthesis from publication-grade packaging
- the final deliverable pipeline is more complete

Why this matters here:

- this repo is excellent at reporting, dashboards, manifests, certainty tables, provenance, and reproducibility artifacts
- but its final output flow is still more report-oriented than publication-oriented

What is worth borrowing:

- explicit post-synthesis revision stages
- publication/export phases
- output pipelines tailored to final deliverable classes rather than generic synthesis only

---

## What should **not** be copied blindly

1. **Do not import AutoResearchClaw’s orchestration heaviness.**
   This repo is cleaner in operational architecture.

2. **Do not copy subsystem breadth without product need.**
   AutoResearchClaw has more research-domain breadth, but that also creates maintenance weight.

3. **Do not replace this repo’s strengths.**
   Keep:
   - provider-instance contracts
   - `RunPaths`
   - security policy resolution
   - dry-run / explain / doctor
   - artifact-first observability

---

## Final judgment

The most valuable things to import from AutoResearchClaw are **not** low-level implementation details. They are higher-order workflow ideas:

- workflow as an explicit state machine
- workflow steps as contracts
- decisions as formal states
- HITL as a policy model
- execution/repair as a dedicated subsystem
- final deliverables as a staged pipeline

The best outcome is not to make this repo look like AutoResearchClaw.
The best outcome is to keep this repo’s operational rigor and combine it with AutoResearchClaw’s stronger research-process modeling.
