# Mega Milestone Plan

## Purpose

This plan merges three roadmap streams into one coherent program:

1. the **completed OpenClaw-inspired hardening milestones** already implemented in this repository (Milestones 1–5)
2. the **AutoResearchClaw adoption/backlog/what-to-borrow** roadmap in `docs/arc/`
3. the **next-step architecture insights** in `docs/next/`

The goal is to stop treating these as separate idea piles and turn them into a single, staged architecture plan.

This is a **program plan**, not just a backlog. It defines:
- what foundation is already complete
- what should happen next
- what depends on what
- what should explicitly NOT be done yet
- how to evolve the repo without losing the strengths it already has

---


## Refined milestone briefs

Agent-ready execution briefs live alongside this plan:
- `doc/megaplan/MM06_ISOLATION_MATURITY.md`
- `doc/megaplan/MM07_WORKFLOW_ARCHITECTURE.md`
- `doc/megaplan/MM08_HITL_POLICY.md`
- `doc/megaplan/MM09_IMPLEMENT_MODE.md`
- `doc/megaplan/MM10_EXECUTION_REPAIR.md`
- `doc/megaplan/MM11_PUBLICATION_PIPELINE.md`
- `doc/megaplan/MM12_DOMAIN_DECOMPOSITION.md`
- `doc/megaplan/MM13_CONTAINER_SANDBOX.md`

Use these when handing work to Copilot/Codex agents so each mega milestone can be executed with the same review cadence used in Milestones 1–5.

---

# Executive summary

This repository is no longer at the “just orchestrate some LLM calls” stage.
It already has serious foundations:

- centralized run paths and artifact discipline
- effective config snapshots
- explain / doctor workflows
- explicit runtime security policy
- sandbox executor and workspace-bounded sandbox execution
- audit trail security/runtime events
- trust semantics on provenance artifacts
- deterministic paper references
- capability-based tool dispatch
- environment shaping for sandboxed subprocesses

That means the next roadmap should **not** start from generic agent fantasies.
It should build on what is already proven.

## Strategic direction

The merged roadmap should proceed in **four major waves**:

1. **Runtime hardening wave** — finish isolation maturity beyond Milestone 5
2. **Workflow architecture wave** — import AutoResearchClaw’s strongest idea: explicit workflow/state/contract modeling
3. **Implementation-product wave** — add a safe `implement` mode for adversarial code work
4. **Research OS wave** — execution/repair, publication pipeline, and domain-bounded contexts

That is the clean merged architecture path.

---

# What is already complete (baseline)

These are no longer roadmap items. They are completed baseline capabilities.

## Completed foundation milestones

### Milestone 1 — policy + explainability
Completed:
- `security:` config section
- `effective_config.json`
- `autoresearch explain config`
- `autoresearch explain resume`
- operator docs for the above

### Milestone 2 — initial runtime enforcement
Completed:
- `RuntimeSecurityPolicy`
- run-scoped workspace path
- `PolicyDeniedError`
- host bash enforcement
- write-boundary enforcement entrypoints
- audit trail sandbox events
- docs for enforcement semantics

### Milestone 3 — diagnostics, trust semantics, deterministic references
Completed:
- `doctor config`
- `doctor output`
- `trust_class` on claims/citations
- `dashboard.json` trust summary
- deterministic references for `paper` output only
- aligned docs

### Milestone 4 — sandbox runtime enforcement
Completed:
- `SandboxExecutor`
- executor-owned workspace creation
- dispatch-level network enforcement
- sandboxed backend subprocesses run from workspace cwd
- doctor/docs updated to reflect real runtime truth

### Milestone 5 — stronger sandbox isolation
Completed:
- executor-owned env shaping contract
- `ToolCapabilities` registry
- capability-based dispatch enforcement
- conservative denial of unclassified tools in sandbox mode (`tool_unclassified`)
- `doctor` sandbox coverage section
- sandbox env shaping wired into real subprocess execution via `CallOptions.process_env`
- aligned docs

## Architectural consequence

Because these five milestones are already done, future plans must assume:
- explicit security policy exists
- diagnostics exist
- sandbox executor exists
- trust/provenance basics exist
- paper references are deterministic
- operator truthfulness is a hard requirement

Any new milestone that ignores that baseline is architecturally wrong.

---

# Guiding principles for the merged roadmap

## 1. Preserve this repo’s existing strengths
From `docs/arc/*`, one thing is crystal clear:
this repo is already stronger than AutoResearchClaw in:

- provider-instance contracts
- runtime security policy resolution
- artifact-path centralization
- dry-run / explain / doctor operator workflows
- manifest / audit / reproducibility discipline
- backend capability normalization

So the roadmap must **preserve these strengths**, not replace them.

## 2. Borrow workflow ideas, not orchestration bloat
What AutoResearchClaw does better is not low-level runtime engineering.
It does better at:
- workflow state modeling
- stage contracts
- formal decision semantics
- richer HITL policy
- execution / validation / repair architecture
- publication pipeline thinking

That is what should be adopted.

## 3. Treat implementation automation as a new product mode
From `docs/next/adversarial-code/automation-insight.md`:
- `run` is for research
- `plan` / `refine` are for documents/specs
- **code implementation requires a first-class `implement` mode**

Do not force code automation into `run`.

## 4. Self-hosting safety is mandatory
From `docs/next/best-architecture/self-hosting-safety-insight.md`:
- this repo should not autonomously self-edit itself by default
- implementation workflows must distinguish:
  - planner/orchestrator repo
  - target repo being modified
- safe defaults must be:
  - `analyze-only`
  - `patch-only`
  - `isolated-apply`

That is not optional. It is a core safety boundary.

## 5. Keep truthfulness as a product rule
Every future milestone must keep this discipline:
- if enforcement is dispatch-level, say dispatch-level
- if a feature is declared but inactive, say that
- if something is partial, say partial

This repo has already paid the price of fixing docs/runtime mismatches. Do not regress.

---

# Mega roadmap structure

The merged roadmap is organized into **8 program milestones** after the already-completed baseline.

- **Program Baseline** — completed Milestones 1–5
- **Mega Milestone 6** — isolation maturity and sandbox backend extensibility
- **Mega Milestone 7** — workflow state machine + phase contracts + shared decision model
- **Mega Milestone 8** — policy-driven HITL and workflow gating
- **Mega Milestone 9** — safe adversarial `implement` mode
- **Mega Milestone 10** — execution / validation / diagnosis / repair subsystem
- **Mega Milestone 11** — publication-grade deliverable pipeline
- **Mega Milestone 12** — domain decomposition into a research operating system
- **Mega Milestone 13** — container-backed sandbox backend (optional/late)

---

# Dependency map

```text
Completed M1-M5
   |
   +--> MM6 isolation maturity
   |
   +--> MM7 workflow states/contracts/decisions
             |
             +--> MM8 HITL policy/gates
             |
             +--> MM9 implement mode
                     |
                     +--> MM10 execution/validation/repair
                     |
                     +--> MM11 publication pipeline
                             |
                             +--> MM12 domain decomposition

MM13 container sandbox backend depends on MM6 and should not start earlier.
```

---

# Program Baseline — already complete

This section exists so future contributors stop reopening solved work.

## Objectives already achieved

### Security/runtime baseline
- explicit `security:` configuration
- pure `RuntimeSecurityPolicy`
- `SandboxExecutor`
- sandbox workspace cwd for subprocesses
- subprocess env shaping via executor-built allowlist
- capability-based dispatch enforcement
- stable denial codes

### Diagnostics baseline
- `explain config`
- `explain resume`
- `doctor config`
- `doctor output`
- security truth table
- sandbox tool coverage diagnostics

### Provenance/reporting baseline
- trust classes on citations and claims
- `dashboard.json` trust summary
- deterministic paper references from tracked citations

### Operator baseline
- `effective_config.json`
- `audit_trail.jsonl`
- docs aligned with runtime truth

## Rule
Do not schedule work that duplicates these capabilities unless it explicitly deepens them.

---

# Mega Milestone 6 — Isolation maturity and sandbox backend extensibility

## Why
Milestone 5 made sandboxing real and tighter, but it is still:
- local-process-based
- dispatch-level for network enforcement
- selective in tool capability coverage

The next step is not containers yet.
The next step is to make the existing local sandbox model **cleaner, broader, and more extensible**.

## Objectives
1. broaden capability coverage beyond today’s classified tools
2. make sandbox/runtime execution coverage easier to reason about
3. make the sandbox backend swappable later without redesign
4. tighten the contract between orchestrator, executor, and backends

## Deliverables

### 6.1 Sandbox backend interface extraction
Create a small interface boundary so `SandboxExecutor` can later delegate to alternate runtime strategies.

Potential modules:
- `src/sandbox/backends/base.py`
- `src/sandbox/backends/local_process.py`

Do NOT implement containers yet.
Just extract the seam.

### 6.2 Capability coverage expansion
Extend `ToolCapabilities` coverage and classification policy for:
- current built-in tools
- future tools
- explicit conservative policy for unknown tools

Add diagnostics for:
- classified coverage percentage
- unknown tool names in effective config
- unsupported capability combinations

### 6.3 Env-shaping policy refinement
Current env shaping is allowlist-based and process-level.
Refine it by:
- formalizing the allowlist rationale
- separating required runtime keys from optional platform keys
- optionally exposing an explain/doctor summary of which env strategy is active

### 6.4 Dispatch contract cleanup
Reduce remaining ad hoc enforcement coupling by ensuring tool-capable execution paths declare:
- whether they use network
- what destination class they target
- whether they may write
- whether they use host shell

### 6.5 Audit enrichments
Add only high-value events, such as:
- executor environment strategy active
- capability coverage warnings
- sandbox backend type in use

## Acceptance criteria
- sandbox runtime path is explicitly backend-extensible
- capability coverage is more complete and better surfaced
- local sandbox semantics remain honest and testable
- no container complexity introduced yet

## Why this milestone comes first
Because it turns the current sandbox from “good enough and real” into “clean enough to build on.”

---

# Mega Milestone 7 — Workflow state machine, phase contracts, shared decisions

This is the **biggest architectural import from AutoResearchClaw**.

## Why
Right now the repo has excellent runtime architecture, but workflow semantics are still distributed across:
- `research_loop.py`
- `document_loop.py`
- `plan_loop.py`
- `orchestrator.py`
- `document_refiner.py`
- `plan_refiner.py`

That makes:
- pause/resume harder to reason about
- HITL policies narrower than they should be
- diagnostics more behavioral than declarative

## Objectives
1. define workflow state models per mode
2. define machine-readable phase contracts
3. unify decision semantics across `run`, `refine`, and `plan`
4. make audit/doctor/explain workflow-aware

## Deliverables

### 7.1 Workflow state modules
Add:
- `src/workflows/research_states.py`
- `src/workflows/refine_states.py`
- `src/workflows/plan_states.py`

Define:
- states
- transitions
- terminal states
- pause states
- resumable states

Suggested common state vocabulary:
- `pending`
- `running`
- `paused`
- `needs_human_input`
- `retrying`
- `completed`
- `failed`

### 7.2 Mode-specific phase enums
Examples:

#### Research phases
- hypothesis
- execute
- critique
- score
- decide
- persist
- compress
- synthesize

#### Refine phases
- builder
- challenger
- personas
- verifier
- hitl_gate
- arbitrator
- persist
- expansion
- indexing

#### Plan phases
Mirror refine where applicable.

### 7.3 Phase contract model
Add:
- `src/workflows/contracts.py`
- `src/workflows/research_contracts.py`
- `src/workflows/refine_contracts.py`
- `src/workflows/plan_contracts.py`

Each contract should define:
- required inputs
- expected outputs
- definition of done
- retry/recovery policy
- human gate flag
- failure codes

### 7.4 Shared decision model
Add:
- `src/workflows/decisions.py`

Normalize decisions like:
- `accept`
- `reject`
- `refine`
- `pivot`
- `retry`
- `defer_human`
- `stale`

Then map current local semantics into it.

### 7.5 State transitions in audit trail
Emit explicit workflow transition events.

### 7.6 Workflow-aware doctor/explain
Teach diagnostics to answer:
- what phase is this run in?
- what is resumable?
- what is missing per contract?
- what human gate is pending?

## Acceptance criteria
- workflow semantics are centralized, not only implicit in code paths
- phase-level correctness becomes diagnosable
- pause/resume and future HITL features have a declared foundation

## Strategic importance
This is the milestone that turns the repo from a disciplined convergence engine into a real workflow platform.

---

# Mega Milestone 8 — Policy-driven HITL and workflow gating

## Why
Current HITL is useful, but relatively narrow:
- verifier deferrals
- interactive questions
- resume handling around uncertainty

AutoResearchClaw’s stronger idea is broader: HITL as workflow policy.

## Objectives
1. make intervention modes configurable
2. attach human gates to meaningful workflow stages
3. support structured guidance injection
4. support review-packet outputs for non-interactive workflows

## Deliverables

### 8.1 Intervention modes
Add config-level modes such as:
- `full_auto`
- `checkpoint_only`
- `decision_only`
- `co_pilot`
- `step_review`

### 8.2 Workflow gates
Potential gates:
- after hypothesis selection in `run`
- before synthesis in `run`
- after verifier classification in `refine`
- after verifier classification in `plan`
- before expansion / indexing phases

### 8.3 Guidance injection model
Store human guidance as a structured artifact that can be injected into the next phase, instead of only answering immediate deferred questions.

### 8.4 Review packet artifacts
For non-interactive flows, emit a structured packet containing:
- current workflow state
- open issues
- candidate decisions
- recommended next action

### 8.5 Workflow-aware HITL diagnostics
Extend doctor/explain to show:
- configured intervention mode
- active/pending human gates
- what guidance is expected

## Acceptance criteria
- HITL becomes a product policy, not only a verifier escape hatch
- workflow state + HITL policy are integrated cleanly
- review packets exist for non-interactive operation

---

# Mega Milestone 9 — Safe adversarial `implement` mode

This milestone merges the two `docs/next/*` insights.

## Why
The repo already has adversarial builder/challenger/verifier/arbitrator patterns.
But for **code implementation work**, the missing capability is not orchestration — it is a dedicated product mode with a safe target model.

## Core rule
Do **not** force implementation automation into `run`.
Do **not** default to self-editing this same repository in place.

## Objectives
1. add a first-class `implement` mode
2. make target-repo separation explicit
3. make patch-only / isolated-apply the safe defaults
4. reuse existing adversarial role architecture

## Deliverables

### 9.1 CLI/product entry
Add something like:
- `autoresearch implement --config ...`

Potential modules:
- `src/implement_loop.py`
- `src/implement_strategy.py`
- `src/implement_runner.py`
- `src/implement_artifacts.py`

### 9.2 Safe target model
Implementation configs must distinguish:
- planner/orchestrator repo
- target repo path
- allowed write roots
- execution level

### 9.3 Execution levels
Support:
- `analyze_only`
- `patch_only`
- `isolated_apply`

Default to `patch_only`.

### 9.4 Adversarial implementation flow
Use existing role pattern:
- Builder -> Copilot Sonnet (or equivalent)
- Challenger -> Codex (or equivalent)
- Verifier -> structured critique classification
- Arbitrator / Rewriter -> accepted critique integration

### 9.5 Artifact model
Persist:
- task normalization
- scope definition
- patch/diff
- critique bundle
- accepted critiques
- final patch set
- audit trail
- rollback/reset instructions

### 9.6 Self-hosting safety rules
Never default to editing the planner repo directly.
If target path equals the planner repo, require explicit high-friction opt-in and still prefer worktree/clone mode.

## Acceptance criteria
- code-task automation has its own product mode
- planner repo and target repo are explicitly separated
- patch-only and isolated-apply are first-class
- self-hosting risks are constrained by architecture, not only by cautionary docs

---

# Mega Milestone 10 — Execution / validation / diagnosis / repair subsystem

This milestone adopts another strong AutoResearchClaw idea.

## Why
The repo already has critique/convergence loops, but it does not yet have a dedicated subsystem for:
- attempting execution
- validating outputs
- diagnosing weakness/failure
- repairing and retrying

That gap matters for both:
- implementation mode
- stronger evidence generation in research mode

## Objectives
1. model execution plans explicitly
2. separate validation from generic critique
3. add diagnosis artifacts
4. add repair loops that are distinct from ordinary scoring/convergence

## Deliverables

### 10.1 Execution plan model
Define an explicit structure for executable attempts:
- target
- environment assumptions
- commands/tools
- expected outputs
- validation expectations

### 10.2 Validator layer
Separate validators from critics.
Validators answer:
- did this execution produce the expected artifact or signal?
- is it structurally valid?

### 10.3 Diagnosis artifacts
When execution/validation fails, emit diagnosis artifacts that explain:
- what failed
- likely cause
- retryability
- recommended repair path

### 10.4 Repair loop
Allow targeted repair/refinement cycles that are separate from generic convergence.

### 10.5 Integration points
Use this subsystem in:
- future `implement`
- research workflows that involve stronger evidence generation

## Acceptance criteria
- execution attempts become explicit, inspectable, and repairable
- validation is a first-class subsystem, not only emergent critique behavior

---

# Mega Milestone 11 — Publication-grade deliverable pipeline

## Why
This repo is already strong in reports, dashboards, manifests, provenance, and HTML/PDF outputs.
But it is still more report-oriented than publication-oriented.

The missing architecture is a formal last-mile pipeline:
- synthesis
- draft
- review
- revision
- packaging/export

## Objectives
1. separate synthesis from publication packaging
2. create deliverable-specific output pipelines
3. strengthen citation verification and export behavior
4. support publication-grade revision stages

## Deliverables

### 11.1 Deliverable pipeline model
Define a staged flow like:
- synthesize
- revise
- package
- export

### 11.2 Deliverable classes
Explicitly support different output classes:
- paper
- technical doc
- executive brief
- decision memo
- future publication/export targets

### 11.3 Citation verification hooks
Build on deterministic references by adding stronger verification/coverage reporting for final deliverables.

### 11.4 Export packaging
Formalize export bundles, potentially including:
- final markdown/html/pdf
- references
- provenance bundle
- manifest
- revision notes

### 11.5 Revision-aware diagnostics
Allow doctor/explain to indicate whether a run is:
- synthesized but not packaged
- packaged but not exported
- export-incomplete

## Acceptance criteria
- final outputs have a staged publication pipeline
- report generation is no longer the only terminal output concept

---

# Mega Milestone 12 — Domain decomposition into a research operating system

## Why
Today the repo is strongest in:
- runtime concerns
- orchestration
- evaluation
- reporting

That is excellent engine architecture.
But the domain model is thinner than it should be.

## Objectives
1. create stronger bounded contexts around research work itself
2. make domain modules more explicit than runtime modules alone
3. support future product breadth without turning the orchestrator into a god object

## Candidate bounded contexts
- literature / sources
- evidence assessment
- workflow contracts
- execution / diagnosis / repair
- deliverable generation
- implementation automation
- HITL policy

## Deliverables
Potential package reshaping over time, for example:
- `src/workflows/`
- `src/evidence/`
- `src/deliverables/`
- `src/execution/`
- `src/implement/`
- `src/hitl/`

This should be gradual, not a big-bang refactor.

## Acceptance criteria
- the repo begins to look like a research operating system, not only a convergence engine
- runtime and domain boundaries become clearer

---

# Mega Milestone 13 — Container-backed sandbox backend (late / optional)

## Why this is late
Because the repo now has a clean local sandbox model and a `SandboxExecutor` boundary.
That should be exploited before introducing container complexity.

## Objectives
1. add a stronger optional sandbox backend behind the same executor contract
2. preserve the existing policy / doctor / explain model
3. avoid rewriting the orchestration layer

## Deliverables
Potentially:
- `src/sandbox/backends/container.py`
- backend selection in sandbox config
- container capability diagnostics in doctor/explain

## Strict guardrails
- no container-first rewrite
- no breaking direct mode
- no pretending container support is universal if it is platform-limited

## Acceptance criteria
- container backend is optional, swappable, and honest about guarantees

---

# Prioritized execution order

## Immediate next order

### Tier 1 — highest leverage
1. **Mega Milestone 6** — isolation maturity and sandbox backend extensibility
2. **Mega Milestone 7** — workflow state + contracts + decisions
3. **Mega Milestone 8** — policy-driven HITL

### Tier 2 — product expansion
4. **Mega Milestone 9** — safe `implement` mode
5. **Mega Milestone 10** — execution / validation / diagnosis / repair

### Tier 3 — maturity expansion
6. **Mega Milestone 11** — publication pipeline
7. **Mega Milestone 12** — domain decomposition

### Tier 4 — optional stronger runtime isolation
8. **Mega Milestone 13** — container-backed sandbox backend

## Why this order
Because:
- stronger workflow architecture should exist before large new product modes
- safe implementation mode should be built on explicit workflow contracts and HITL policy
- containerization is infrastructure polish, not the next core architectural win

---

# Recommended milestone slicing into agent-executable workstreams

## Workstream A — Runtime hardening track
- MM6
- MM13

## Workstream B — Workflow architecture track
- MM7
- MM8

## Workstream C — Product expansion track
- MM9
- MM10
- MM11

## Workstream D — Domain architecture track
- MM12

This allows planning without collapsing everything into one mega refactor.

---

# Suggested acceptance gates for each mega milestone

Every future mega milestone should include these gates:

## Gate 1 — Runtime truthfulness
- docs match code
- doctor/explain reflect actual behavior

## Gate 2 — Artifact clarity
- new workflow/product stages emit explicit artifacts
- no hidden runtime-only state if resumability depends on it

## Gate 3 — Operator visibility
- doctor/explain can diagnose the new feature
- audit trail includes meaningful state transitions/events

## Gate 4 — Safe defaults
- features default to the least surprising and least destructive mode
- especially true for implementation automation

## Gate 5 — No architecture regression
- preserve provider-instance contracts
- preserve `RunPaths`
- preserve security policy purity
- preserve explain/doctor quality

---

# What should explicitly NOT be done

## Do not:
- rewrite the repo into AutoResearchClaw shape wholesale
- collapse `run`, `plan`, `refine` into one monolithic super-loop
- force code implementation into `run`
- default any future `implement` workflow to self-editing this repo in place
- jump to Docker before the local sandbox backend boundary is fully exploited
- overclaim kernel/container guarantees from process-level isolation
- lose the artifact-first discipline that already differentiates this repo

---

# Concrete next action recommendation

If this plan is to be executed soon, the best next concrete move is:

## Start with Mega Milestone 6 planning brief
Why?
Because it is the clean bridge from the completed M1–M5 security/runtime work into the bigger ARC-inspired architecture work.

After that:
- do Mega Milestone 7 in detail
- then Mega Milestone 8
- only then start the first safe `implement` milestone design

That sequence is the highest-leverage path.

---

# Final judgment

The merged plan is not:
- “become AutoResearchClaw”
- “just add containers”
- “just add code agents”

The correct merged roadmap is:

1. preserve the strong runtime/operator foundations already built here
2. import AutoResearchClaw’s workflow/state/contract strengths
3. add a safe implementation mode with target-repo separation
4. grow toward a research operating system deliberately, not theatrically

That is the architecture path with the best long-term payoff and the lowest risk of turning this repo into spaghetti with nice slogans.
