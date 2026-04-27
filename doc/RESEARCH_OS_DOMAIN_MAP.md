# Research OS — Domain Map

**Milestone:** MM12 — Domain Decomposition into a Research Operating System
**Status:** living document — updated as bounded contexts are formalized

---

## Purpose

This map records the target bounded contexts, their responsibilities, and the
current file ownership for each.  It is the authoritative reference for MM12
refactoring decisions and serves as a contract for where new modules should
land.

---

## Target Bounded Contexts

### 1. Research Orchestration

**Responsibility:** drive the core adversarial research loop — planning,
iteration, scoring, convergence, and run lifecycle management.

| File | Role |
|---|---|
| `src/research_loop.py` | Top-level loop driver |
| `src/config.py` | Research config model and validation |
| `src/strategy.py` | Execution strategy selection |
| `src/orchestrator.py` | Multi-run / portfolio orchestration |
| `src/scorer.py` | Iteration scoring and convergence |
| `src/semantic_eval.py` | Semantic similarity evaluation |
| `src/run_state.py` | In-flight run state |
| `src/run_io.py` | Run I/O helpers |
| `src/run_finalize.py` | Post-run finalisation |
| `src/run_metadata_artifacts.py` | Run-level metadata writing |
| `src/run_paths.py` | Canonical artifact path layout |
| `src/dry_run.py` | Dry-run/preview mode |

**Target package seam:** `src/research/` (or keep at top level — this context
is already relatively cohesive; Step 2 targets evidence and deliverables first)

---

### 2. Evidence

**Responsibility:** accumulate, deduplicate, and persist the knowledge produced
during research — knowledge base, citations, references, and reproducibility
artefacts.

| File | Role |
|---|---|
| `src/knowledge_base.py` *(if present)* | KB assembly |
| `src/references.py` | Deterministic references section builder/extractor |
| `src/artifacts.py` | Generic artifact helpers |
| `src/evaluation_artifacts.py` | Evaluation-specific artifacts |
| `src/run_metadata_artifacts.py` | Run metadata persistence |
| `src/reproducibility.py` | Reproducibility record |
| `src/research_logs.py` | Research log persistence |
| `src/agreement_artifacts.py` | Multi-model agreement artifacts |
| `src/certainty.py` | Certainty / confidence tracking |
| `src/comparison.py` | Source comparison utilities |
| `src/constraints.py` | Research constraint models |
| `src/provenance.py` | Provenance tracking |
| `src/provenance_artifacts.py` | Provenance artifact models |
| `src/provenance_pipeline.py` | Provenance pipeline |

**Target package seam:** `src/evidence/`

---

### 3. Deliverables / Publication Pipeline

**Responsibility:** stage synthesis through revision, packaging, export, and
citation verification into publication-grade deliverables.

| File | Role |
|---|---|
| `src/deliverable_pipeline.py` | Staged pipeline model (MM11 Step 1) |
| `src/deliverable_classes.py` | Class configs and factory (MM11 Step 2) |
| `src/citation_verification.py` | Citation/export verification (MM11 Step 3) |
| `src/export_bundle.py` | Export bundle assembly (MM11 Step 4) |
| `src/pdf_report.py` | PDF report generation |
| `src/reporting.py` | Report generation orchestration |
| `src/report_exports.py` | Report export helpers |
| `src/output_style.py` | Output style config and presentation |

**Target package seam:** `src/deliverables/`

---

### 4. Execution / Implement

**Responsibility:** plan, execute, validate, diagnose, and repair
implementation-automation work; bridge research outputs to code changes.

| File | Role |
|---|---|
| `src/implement_loop.py` | Implement-mode loop driver |
| `src/implement_runner.py` | Runner and step executor |
| `src/implement_strategy.py` | Implement strategy models |
| `src/execution_plan.py` | Execution plan model (MM10) |
| `src/execution_validator.py` | Execution result validator (MM10) |
| `src/execution_diagnosis.py` | Diagnosis artifact model (MM10) |
| `src/execution_integration.py` | Adapter layer bridging loops to execution subsystem (MM10) |
| `src/repair_loop.py` | Execution repair loop (MM10) |
| `src/plan_loop.py` | Plan-mode loop |
| `src/plan_refiner.py` | Plan refinement |
| `src/plan_strategy.py` | Plan strategy models |
| `src/document_loop.py` | Document-mode loop |
| `src/document_refiner.py` | Document refinement |
| `src/document_strategy.py` | Document strategy models |

**Target package seam:** `src/execution/` + `src/implement/`

---

### 5. Workflow State Machine

**Responsibility:** explicit workflow states, transitions, gates, and HITL
review packets — the control-flow layer independent of any specific loop.

| File | Role |
|---|---|
| `src/workflows/__init__.py` | Package init |
| `src/workflows/contracts.py` | Workflow contract models |
| `src/workflows/decisions.py` | Decision records |
| `src/workflows/gates.py` | Gate conditions |
| `src/workflows/guidance.py` | Guidance payloads |
| `src/workflows/transitions.py` | State-transition definitions |
| `src/workflows/research_states.py` | Research-specific states |
| `src/workflows/implement_states.py` | Implement-specific states |
| `src/workflows/plan_states.py` | Plan-specific states |
| `src/workflows/refine_states.py` | Refine-specific states |
| `src/workflows/review_packet.py` | HITL review packet model |

**Already a package seam** — `src/workflows/` is the cleanest bounded context
in the repo.

---

### 6. HITL / Policy

**Responsibility:** human-in-the-loop pause/resume logic, policy denial, and
trust decisions — independent of loop orchestration.

| File | Role |
|---|---|
| `src/hitl.py` | HITL pause/resume and artifact management |
| `src/policy_denial.py` | Policy denial model and enforcement |
| `src/trust.py` | Trust model |
| `src/security_runtime.py` | Runtime security enforcement |
| `src/tool_capabilities.py` | Tool capability declarations |
| `src/tool_runtime.py` | Tool runtime dispatch |
| `src/sandbox_executor.py` | Sandbox executor |
| `src/sandbox/` | Sandbox backends |

**Target package seam:** `src/policy/` for HITL/trust/denial;
`src/sandbox/` already exists.

---

### 7. Diagnostics / Observability

**Responsibility:** inspect config and run health without side effects; explain
effective configuration and pipeline state to operators.

| File | Role |
|---|---|
| `src/doctor.py` | Config and run health checks (MM11 Step 5) |
| `src/explain.py` | Human-readable config/pipeline explainer (MM11 Step 5) |
| `src/audit_trail.py` | Immutable audit log |
| `src/runtime_telemetry.py` | Runtime telemetry collection |

**Target package seam:** `src/diagnostics/`

---

### 8. Infrastructure / Backends

**Responsibility:** CLI entrypoints, LLM backend adapters, templates, and
cross-cutting runtime utilities.

| File | Role |
|---|---|
| `src/cli.py` | Unified CLI (`research`, `implement`, `doctor`, `explain`, …) |
| `src/backends/` | LLM backend adapters (already a package) |
| `src/templates/` | Prompt/report templates (already a package) |
| `src/backend_options.py` | Backend option helpers |
| `src/provider_instances.py` | Provider instance construction |
| `src/prompts.py` | Prompt construction utilities |
| `src/portfolio.py` | Portfolio / multi-topic run helpers |

**Already partially packaged** — `src/backends/` and `src/templates/` are clean.

---

## Gap Analysis

| Context | Current state | Gap |
|---|---|---|
| Research Orchestration | flat in `src/` | large; tolerable for now |
| Evidence | flat in `src/` | scattered across artifact helpers |
| Deliverables | flat in `src/` | coherent — ready for `src/deliverables/` |
| Execution / Implement | flat in `src/` | coherent — ready for `src/execution/` |
| Workflow State Machine | `src/workflows/` ✓ | clean |
| HITL / Policy | flat in `src/` | policy and sandbox partially separable |
| Diagnostics | flat in `src/` | small surface — easy to extract |
| Infrastructure / Backends | `src/backends/`, `src/templates/` ✓ | CLI still flat |

---

## Refactoring Order (MM12 Steps 2–5)

| Step | Action | Commit | Status |
|---|---|---|---|
| Step 2 | Introduce `src/deliverables/` and `src/evidence/` package seams | `refactor: introduce domain package seams` | ✅ done (`194b95f`) |
| Step 3 | Carve out `src/execution/` and `src/implement/` | `refactor: separate execution and implement bounded contexts` | ✅ done (`53d78aa`) |
| Step 4 | Isolate HITL/policy into `src/policy/` | `refactor: isolate hitl policy boundaries` | ✅ done (`6691c3a`) |
| Step 5 | Update docs and diagnostics to reflect domain architecture | `docs: align research os bounded contexts` | ✅ done (`fbaf8c0`) |

---

## Principles

1. **No big-bang refactor** — seams are introduced incrementally; existing
   imports continue to work via `__init__.py` re-exports during migration.
2. **Tests stay green** — each step commits with a passing full suite.
3. **Diagnostics lead** — `doctor` and `explain` are updated alongside or
   immediately after each structural change.
4. **Bounded context = independent testability** — if a context cannot be
   imported and tested in isolation, the seam is not yet clean.
