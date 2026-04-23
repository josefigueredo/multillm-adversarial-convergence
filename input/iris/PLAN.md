# Iris Playground — Consolidated Plan

**Status:** Merged draft pending sign-off (consolidates `PLAN.md` v4 and `PLAN_CODEX.md`)
**Author:** Architecture
**Date:** 2026-04-23
**Supersedes:** `PLAN.md`, `PLAN_CODEX.md` — this document is the active planning artifact once signed off.
**Lineage retained:** both predecessor files remain on disk for history and review context. `PLAN.md` is the structural draft this artifact inherited from; `PLAN_CODEX.md` is the critique that shaped it and continues to serve as an architectural guardrail reviewers can consult independently.
**Relationship to predecessors:**
- `PLAN.md` contributed the concrete structure: deployables, modes, milestones, decisions, sequencing, acceptance.
- `PLAN_CODEX.md` contributed the principles and guardrails that shaped the structure.
- This file merges both — principles first, then concrete plan — so a reader gets discipline and actionable detail in one artifact.

---

## 1. Purpose

The playground is the living development environment where Iris converges from validated PoCs toward the MVP defined in [`V1_ALPHA_VERTICAL_SLICE.md`](../../codename-iris/docs/product/V1_ALPHA_VERTICAL_SLICE.md).

Unlike `pocs/` — atomic, disposable proofs — the playground is a living system that receives production-structured code, evolves through iterations, and exposes regressions through git history.

The playground is not a product. It is the path to one.

---

## 2. Principles and Guardrails

These principles shape every decision in this plan. Violating any of them is a revision trigger, not a local override.

1. **Capability-first, not service-count-first.** The system's required behavior is fixed; the number of deployables that realize it is an implementation choice driven by operational evidence.

2. **Honest classification of decisions.** Every decision falls in exactly one of three tiers:
   - **Settled** — supported by main-repo evidence (ratified PoCs, ADRs, strategy docs).
   - **Temporary implementation default** — needed so the playground can move; must not be referenced as "decided architecture."
   - **Open question** — acknowledged; may promote to settled when building produces evidence.

3. **The playground earns its microservices.** Start with fewer deployables. Split only when a concrete signal appears: scale divergence, runtime isolation need, team ownership split, or observability demand.

4. **Shared assets are stable where proven, versioned where converging.** Versioning during convergence is honesty, not bureaucracy. Graduating an asset to unversioned is an explicit promotion.

5. **Local Kubernetes is non-negotiable.** External integrations are toggleable modes, not stages in a progression. The playground must remain fully runnable locally with no external dependency.

6. **PoCs are evidence, not scaffolds.** The playground may learn from PoCs and port code under constrained rules, but must have **zero runtime dependency** on `pocs/`. Delete `pocs/` — the playground still runs.

7. **Contract enforcement is boundary-focused, not universal.** Strict schema validation where corruption has cost; static typing and tests elsewhere.

8. **Boundaries stay explicit even under single-language implementations.** Python-first is a speed concession, not a structural one. Capability-domain ownership remains visible in package/module structure.

---

## 3. Scope

### In scope
- End-to-end realization of the alpha vertical slice.
- **Capabilities** from all six capability domains (Evidence, Knowledge, Intelligence, Decision, Execution, Governance). Domain boundaries preserved in code structure, not necessarily in deployable count.
- Runtime schema enforcement at boundaries that matter (see §10).
- OTel tracing correlated by `pipeline_run_id` end-to-end.
- Fixtures sufficient to execute 35 golden test cases (5 per action class × 7 classes).

### Out of scope (deferred)
- Slack ingress, Confluence/GitHub ingestion, regulated-tier deployment, visual corpus, executive summary generation beyond minimum alpha shape.

### Explicitly not scope of this plan
- Any architectural direction not documented in the main Iris repo. New architecture requires an ADR before entering this plan.

---

## 4. Required Capabilities (for Alpha)

These capabilities must exist before `milestone-mvp-candidate`. How they are realized — in how many deployables, across which packages — is an implementation decision, not an architectural one:

1. Jira ingestion (seed + ongoing)
2. Normalization to the canonical `NormalizedEvidenceRecord`
3. Deduplication
4. Clustering (≥5 tickets, ≥2 weeks)
5. Ranking (frequency × severity)
6. Resolution Memory retrieval (tenant-scoped, freshness-weighted)
7. Action classification (7 canonical classes, grounded in corpus or pattern evidence)
8. Trust labeling (grounded / heuristic / mixed)
9. Recommendation generation (evidence-linked, actionable)
10. Review queue state machine (pending → approved / rejected / needs_refinement)
11. Manager-facing dashboard publication
12. End-to-end observability with `pipeline_run_id` correlation
13. Acceptance gating and withholding logic (minimum credible insight standard)

---

## 5. Deployables (Initial Target)

The product docs define **capability domains**, not **deployable counts**. This plan targets **3–4 deployables maximum for the initial playground iteration, biased toward fewer**.

**Preferred starting shape (3 deployables):**

| Deployable | Responsibility | Capability domains it spans |
|---|---|---|
| `connector` | Jira auth, fetch, pagination, rate-limit backoff, normalization to `NormalizedEvidenceRecord` | Evidence |
| `pipeline-worker` | Temporal worker hosting activities for dedupe → cluster → rank → corpus retrieval → classify → trust label → recommend | Intelligence, Knowledge, Decision |
| `product-api` | Review queue (persistence, state machine, reviewer API, audit lineage, action_class locking) + dashboard read-side aggregation behind one product-facing API | Decision, Governance, Execution |

**Fallback shape (4 deployables):** split `product-api` into `review-queue-api` and `dashboard-api` **only if** the first wiring reveals a concrete boundary muddying — for example, reviewer write paths contending with dashboard read paths, or divergent deployment cadences. Don't pre-split.

**Rules:**
- Domain boundaries exist as **package/module boundaries inside each deployable**, not network boundaries.
- `pipeline-worker` runs 7 pipeline activities internally, not 7 microservices. Temporal activities preserve sequencing and retry semantics; network partitioning between them is premature.
- Deployable count is a playground construction decision, not an architecture commitment. The product repo is free to make different choices.

---

## 6. Runtime Modes (Orthogonal, Not Sequential)

Two runtime modes, toggleable per deployable via environment config:

| Mode | Jira | Bedrock | Qdrant | Use when |
|---|---|---|---|---|
| `local-complete` | File-backed fixture | Stub returning fixed structured outputs | In-cluster kind pod | Iteration, determinism, offline work, CI |
| `integration-real` | Real OAuth against a test tenant | Real Bedrock via LiteLLM | In-cluster kind pod (same) | Acceptance testing, pre-MVP dress rehearsal |

**Rule:** Both modes run on the same kind cluster. Only external dependencies flip.

---

## 7. Evolution Model — Mainline + Tags, Not Parallel Eras

One active mainline. Git handles history.

| Mechanism | Purpose |
|---|---|
| **Milestone tags** | Mark convergence points: `milestone-wire-done`, `milestone-harden-done`, `milestone-mvp-candidate`. Checkout any tag to reproduce that state. |
| **Snapshot branches** | Cut a branch only before risky refactors or when we explicitly want side-by-side comparison. Merge back or delete — do not keep indefinitely. |
| **No permanent parallel eras on disk** | Permanent runnable eras create maintenance debt without proportional value. Rejected. |

**Milestones:**

| Milestone tag | Acceptance | Modes expected to work |
|---|---|---|
| `milestone-wire-done` | First E2E trace completes; one golden case produces a review-queue item | `local-complete` |
| `milestone-harden-done` | 35-case golden suite passes; 10 withholding conditions enforced; minimum credible insight gate live | `local-complete` + `integration-real` |
| `milestone-mvp-candidate` | `V1_ALPHA_VERTICAL_SLICE.md` done-definition met; alpha scorecard green on one week simulated traffic | Both, at parity |

---

## 8. Folder Structure

```
playground/
├── PLAYGROUND_PLAN.md              ← this document (canonical)
├── PLAN.md                         ← superseded draft, kept as lineage
├── PLAN_CODEX.md                   ← critique / architectural guardrail, kept as counterweight
├── README.md                       ← orientation for humans entering the folder
├── shared/                         ← cross-deployable assets
│   ├── contracts/
│   │   └── v1alpha/                ← JSON schemas; version when they converge
│   ├── fixtures/
│   │   ├── jira-seed/              ← closed tickets for RM cold-start
│   │   ├── jira-open/              ← open tickets for ongoing ingestion
│   │   ├── tenant-configs/         ← standard-tier baseline
│   │   └── golden-cases/
│   │       └── v1/                 ← 35 cases; version as they evolve
│   ├── prompts/
│   │   ├── classify/
│   │   │   └── v1/
│   │   └── recommend/
│   │       └── v1/
│   └── observability/              ← OTel/Grafana/Tempo/Loki config (based on poc-007)
├── spine/                          ← kind cluster bootstrap (based on poc-spine-bootstrap)
├── deployables/                    ← reflects preferred 3-deployable shape; product-api may split later
│   ├── connector/
│   ├── pipeline-worker/
│   └── product-api/
├── slices/
│   └── slice-01-jira-to-dashboard/ ← wiring + acceptance tests for the alpha slice
└── modes/                          ← env overlays for local-complete vs integration-real
    ├── local-complete/
    └── integration-real/
```

**Rules:**
- `shared/` is stable where proven stable and versioned where converging.
- No runtime dependency from `playground/` into `pocs/`. Playground must run if `pocs/` is deleted.

---

## 9. Decisions Settled (by PoC Evidence)

Settled = supported by runtime-validated PoC evidence in the main repo.

| # | Decision | Source | Why settled |
|---|---|---|---|
| **D1** | `TriageWorkflow` and `PipelineWorkflow` can coexist in the same Temporal namespace without collision. | poc-083 | Runtime-validated — coexistence works if/when we split. |
| **D2** | Triage queue is PostgreSQL-materialized, not NATS-ephemeral. | poc-084 | Operator visibility after consumption requires durable state. |
| **D3** | L3 confirmation timeout default = 300s; per-tenant override via tenant spec; resolved at workflow start. | poc-085 | Runtime-validated per-tenant config propagation. |
| **D4** | Slack → `NormalizedEvidenceRecord` mapping schema `slack-thread-message-to-evidence-model-v1` is canonical when Slack ingress is added. | poc-086 | Schema fixed — applies out of alpha scope. |
| **D5** | Cross-tenant anonymization schema `cross-tenant-anonymization-v1` (stripped/hashed/retained) is canonical at the shared-improvement boundary. | poc-087 | Schema fixed — applies v1.x / v2. |

---

## 10. Temporary Implementation Defaults (Treatment Differs)

These resolve placeholders in the main architecture docs. They are **not settled**. Treatment differs by architectural weight.

| # | Default | Resolves | Treatment |
|---|---|---|---|
| **P1** | Corpus retrieval happens ONCE per pipeline, invoked by Intelligence, passed to Decision via the DAG. | `CAPABILITY_DOMAIN_BOUNDARIES.md` §3.4 placeholder. | **ADR track.** P1 affects workflow shape, cost model, Knowledge/Intelligence/Decision interaction, and future refactor difficulty. Draft `ADR-024` in the main repo before `milestone-harden-done`. |
| **P2** | For initial wiring, use a single branching `PipelineWorkflow`. Revisit splitting into `TriageWorkflow` + `PipelineWorkflow` after the first stable end-to-end slice. | `REALTIME_TRIAGE_FLOW.md` §3 placeholder. | **Temporary implementation default.** P2 reads as orchestration convenience, not durable architecture. Do NOT draft an ADR yet. Revisit only if the first stable slice proves P2 is durable rather than temporary. |

**Rule:** Nothing labeled `P*` here gets referenced in code comments or docs as "decided." P1 becomes `ADR-024` when playground evidence is ready. P2 remains playground-internal until evidence promotes or demotes it.

---

## 11. Contract Enforcement (Boundary-Focused)

Runtime JSON schema validation is enforced **only at boundaries that matter**:

| Boundary | Contracts enforced |
|---|---|
| External ingress (Jira → connector) | `ConnectorSourceRecord` (inbound shape) |
| Inter-deployable handoff (connector → pipeline-worker via NATS) | `NormalizedEvidenceRecord` |
| Persistence writes (pipeline-worker → product-api DB) | `Recommendation`, `ReviewQueueItem` |
| Publication (product-api dashboard output) | `ActionOutputEnvelope` |
| Governance output (autonomy evaluation) | `AutonomyDecisionResult` |

**Not enforced at runtime:**
- In-process activity-to-activity handoffs inside `pipeline-worker` (use static typing instead).
- Value enums like `ActionClass` (enforce via type system, not JSON schema).

The nine named contracts still exist and are documented in `shared/contracts/v1alpha/`. Enforcement posture varies by location.

---

## 12. PoC → Playground Boundary Policy

The whole point of this artifact is to cross this boundary. Rules:

1. **PoCs are reference evidence, not production scaffolds.** A PoC's purpose was to validate one claim; its code shape is not obligated to match product structure.
2. **Playground may port code from PoCs** only when the boundary it encodes is still valid and runtime assumptions still hold. Port means rewrite into product structure (packages, contracts, error handling), not copy verbatim.
3. **Playground must have zero runtime dependency on any `pocs/` folder.** Delete `pocs/`, playground still runs. If this is untrue, it's a bug.
4. **When a PoC pattern conflicts with product structure**, reimplement cleanly. Do not warp playground code to preserve PoC shape.
5. **Cite but do not couple.** `shared/observability/README.md` can say "based on poc-007" — but must not `include`, `import`, or `kubectl apply` from that path.

---

## 13. Language Posture

**v1 (through `milestone-wire-done` and `milestone-harden-done`): Python only, with one binding condition.**

**Condition:** Python-only is acceptable **only if domain boundaries remain explicit in package/module structure**, and boundary contracts remain clear in code. Single-language must not become single-script-soup. Each deployable organizes its code around capability domains (`evidence/`, `intelligence/`, `knowledge/`, `decision/`, `governance/`, `execution/` as applicable), and inter-domain calls traverse explicit interfaces with the same contract rigor as if they crossed a network.

Rationale: Python handles the Temporal SDK, Qdrant client, LiteLLM, HTTP APIs, and AI/ML adequately. Single build chain, single test harness, single container base image. Polyglot before product-shape clarity is premature friction. Python-only is a speed concession, not a structure concession.

**Introducing Go** is allowed only when a specific deployable demonstrates need (throughput pressure, strong-type safety critical to a public API, team capability). The `product-api` is the most plausible first candidate — revisit at `milestone-harden-done`.

---

## 14. Sequencing

Each step produces a commit. No step is skipped.

1. **Sign-off on this plan.** No scaffolding until approved.
2. **Scaffold `shared/`, `spine/`, `deployables/`, `slices/`, `modes/`.** Stubs only. README per folder.
3. **Bootstrap `iris-playground` kind cluster** from `spine/` (based on poc-spine-bootstrap patterns, ported cleanly — no runtime coupling).
4. **Implement `connector` in `local-complete` mode.** File-backed Jira fixture. Publishes to NATS.
5. **Implement `pipeline-worker` skeleton.** Temporal worker running one dummy activity; verify registration and task-queue routing.
6. **Implement `product-api` skeleton.** PostgreSQL schema for review queue, create+fetch endpoints, placeholder dashboard read endpoint.
7. **Wire slice-01 end-to-end in `local-complete`** with stub activities and Bedrock stub. One golden case completes.
8. **Tag `milestone-wire-done`.**
9. **Replace stubs with real logic.** Deduplication, clustering, real prompts, real classification against LiteLLM+Bedrock. Golden suite grows to 35 cases.
10. **Enable `integration-real` mode.** Real Jira OAuth, real Bedrock via LiteLLM. Same golden suite must pass.
11. **Draft `ADR-024` for P1** based on what building taught us. **Reassess P2** — promote to ADR only if evidence shows it's durable architecture; otherwise keep it as a temporary implementation default or demote it to "not a decision at all."
12. **Tag `milestone-harden-done`.**
13. **Close to alpha scorecard.** One week simulated traffic. Tag `milestone-mvp-candidate`.

---

## 15. Acceptance Criteria Per Milestone

### `milestone-wire-done`
- ✅ All planned initial deployables reachable in `iris-playground` namespace (3 for preferred shape; 4 if `product-api` was already split)
- ✅ One golden case yields a review-queue item with every required field populated
- ✅ OTel trace with `pipeline_run_id` correlation spans every deployable in the active shape
- ✅ Works in `local-complete` mode

### `milestone-harden-done`
- ✅ 35-case golden suite passes
- ✅ All 10 withholding conditions from `ACCEPTANCE_CRITERIA_V1.md` §6 enforced
- ✅ Works in both `local-complete` and `integration-real` modes at parity
- ✅ `ADR-024` drafted for P1 (corpus retrieval call site)
- ✅ P2 reassessed — either remains temporary default, gets promoted to ADR, or gets demoted to "not a decision at all"

### `milestone-mvp-candidate`
- ✅ `V1_ALPHA_VERTICAL_SLICE.md` done-definition met
- ✅ `ALPHA_SUCCESS_SCORECARD.md` green on one week simulated traffic
- ✅ Reviewer can complete end-to-end work

---

## 16. Bottom-Line Recommendation

### Approve
- The existence of a separate playground distinct from `pocs/`.
- Local Kubernetes as the runtime substrate.
- Iterative progression toward the alpha slice via milestones.
- Use of PoC evidence to inform playground construction under the boundary policy in §12.
- The 3-deployable preferred shape with 4-deployable fallback under concrete evidence.
- Python-first posture under the boundary-preservation condition in §13.

### Explicitly Reject (from earlier drafts; captured to prevent drift)
- Fixed 11-service decomposition from day one.
- Treating unresolved architecture placeholders as locked decisions.
- "Shared is versionless" absolutism.
- Permanent fully runnable parallel eras as the default model.
- Blanket runtime schema enforcement at every internal hop.

---

## 17. Open Questions Requiring Sign-Off

Only one remains:

1. **Plan location after approval** — stays at `playground/PLAYGROUND_PLAN.md`, or promotes to `docs/` in the main Iris repo as a platform strategy doc?

Resolved in prior revisions (documented here to prevent drift):
- ~~Deployable count~~ → 3–4 max, biased toward fewer; 3-deployable shape preferred, 4 as fallback only when boundary muddying is demonstrated (§5).
- ~~Language stance~~ → Python-only through harden, with binding condition that domain boundaries remain explicit in package/module structure (§13).
- ~~ADR ownership~~ → `ADR-024` for P1 before `milestone-harden-done`; P2 stays as temporary playground default, no ADR planned (§10).

---

**No playground scaffolding begins until this plan is signed off.**
