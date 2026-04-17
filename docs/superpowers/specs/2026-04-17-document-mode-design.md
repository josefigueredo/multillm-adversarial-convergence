# Document Mode — Design Spec

**Date:** 2026-04-17
**Status:** Approved
**Scope:** auto-research — new `DocumentRefiner` sibling class + `ConvergeStrategy`

---

## 1. Problem

auto-research runs a knowledge accumulation loop: each accepted iteration appends findings to `knowledge_base.md`. That model works for research. It fails for document production, where the goal is artifact convergence — a single canonical document refined across adversarial cycles until no verified critiques remain.

This spec adds a `document` mode to auto-research that runs a Builder → Challenger → Personas → Verifier → Arbitrator → patch cycle, terminating when zero verified critiques emerge across one full cycle.

**Origin:** Multi-LLM Collaboration Protocol (`Acme-platform-multi-llm-collaboration` repo), observed from the Iris PRD development session (April 2026).

---

## 2. Architecture

### 2.1 New files

```
auto-research/
├── src/
│   ├── document_refiner.py    # DocumentRefiner — sibling to AutoResearcher
│   ├── document_loop.py       # run_cycle(), CycleContext, CycleState
│   ├── document_strategy.py   # ConvergeStrategy — standalone, NOT in strategy.py
│   └── hitl.py                # HumanInputRequest, HumanDecision, interactive + async collection
│
├── prompts/
│   ├── prd_builder.md
│   ├── prd_challenger.md
│   ├── prd_verify.md
│   ├── prd_arbitrate.md
│   ├── prd_persona_architect.md
│   ├── prd_persona_scrum_master.md
│   ├── prd_persona_product_owner.md
│   ├── generate_readme.md
│   └── generate_docs_index.md
│
├── configs/
│   └── prd_template.yaml
│
└── tests/
    ├── test_document_loop.py
    ├── test_document_refiner.py
    └── test_document_strategy.py
```

### 2.2 Unchanged files

`orchestrator.py`, `research_loop.py`, `run_state.py`, `scorer.py` — untouched. All existing research configs and the `run` CLI subcommand continue to work as before.

### 2.3 Modified files

| File | Change |
|---|---|
| `src/config.py` | Add `PersonaConfig`, `ArtifactConfig`, `DocumentConfig` — loaded independently by `refine` subcommand, no changes to `ResearchConfig` |
| `src/cli.py` | Add `refine` subcommand; routes to `DocumentRefiner` when `document:` key is present in config. Does NOT route through strategy factory. |
| `src/run_state.py` | Extract `BaseContext` — shared callback base for both `LoopContext` and `CycleContext` |

---

## 3. Cycle Execution

Each document cycle runs five steps in sequence:

```
Builder          → produces primary artifact (cycle 1) or applies validated patches (cycle N+)
Challenger       → internal consistency critique with mandatory section references
Personas         → stakeholder critique (parallel or serial per config)
Verifier         → reads artifact at each section_ref → VALID / STALE / DEFER(reason)
                     DEFER reasons: out_of_scope | needs_research | human_required
Human gate       → if any human_required deferrals: pause and collect answers (interactive
                   or async). Inject decisions into CycleContext before continuing.
Arbitrator       → generates patch proposals for VALID critiques only
Builder          → applies patches, writes new artifact version
Issue registry   → updated with lifecycle state and defer_reason per critique
Convergence check → clean only when: zero VALID AND zero human_required
```

**Termination:** when `consecutive_clean_cycles >= config.convergence_cycles` (default: 1). Also terminates on `max_cycles` if set.

---

## 4. Data Model

### 4.1 `CycleState`

`prd_path` derives from `DocumentConfig.primary_artifact` — not hardcoded.

```python
@dataclass
class CycleState:
    prd: str = ""
    prd_path: Path = field(default_factory=lambda: Path("PRD.md"))  # set from config.primary_artifact
    prd_versions: list[str] = field(default_factory=list)
    cycle: int = 0
    issue_registry: list[Issue] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    pending_human_inputs: list[HumanInputRequest] = field(default_factory=list)
    human_decisions: list[HumanDecision] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    results_path: Path = field(default_factory=lambda: Path("results.tsv"))
```

### 4.2 `Issue`

```python
@dataclass
class Issue:
    id: str                      # "I-01", "I-02", ...
    description: str
    raised_by: str               # "challenger" | persona name
    cycle: int
    section_ref: str             # PRD section reference (required)
    status: str                  # "open" | "valid" | "stale" | "deferred" | "resolved"
    defer_reason: str | None = None   # "out_of_scope" | "needs_research" | "human_required"
    verified_cycle: int | None = None
    patch_applied: bool = False
```

### 4.4 HITL data structures

```python
class DeferReason:
    OUT_OF_SCOPE    = "out_of_scope"     # skip — does not block convergence
    NEEDS_RESEARCH  = "needs_research"   # pipeline can resolve — does not block convergence
    HUMAN_REQUIRED  = "human_required"   # BLOCKS convergence until answered

@dataclass
class HumanInputRequest:
    issue_id: str           # links back to Issue.id
    question: str           # what the human must answer — written by the Verifier
    context: str            # PRD section text + critique that raised this
    suggested_answer: str   # Verifier's best guess — shown for fast confirmation
    cycle: int

@dataclass
class HumanDecision:
    issue_id: str
    question: str
    answer: str             # human-provided or confirmed suggested answer
    answered_at: str        # ISO timestamp
    answered_by: str        # "human" | "auto-confirmed" (human accepted suggestion)
```

### 4.3 `BaseContext` and `CycleContext`

`BaseContext` holds the 4 callbacks shared with the research loop. `CycleContext` extends it with 2 document-specific callbacks. When the orchestrator changes cost tracking, only `BaseContext` changes — both loops stay in sync automatically.

```python
@dataclass
class BaseContext:
    """Shared callback bundle — used by both LoopContext and CycleContext."""
    call_with: Callable[..., AgentResponse]
    invoke_for_strategy: Callable[..., AgentResponse]
    track_usage: Callable[[AgentResponse, str], None]
    track_cost: Callable[[float, str], None]

@dataclass
class CycleContext(BaseContext):
    """Document-loop additions."""
    config: DocumentConfig
    read_prd_section: Callable[[str], str]
    update_issue_registry: Callable[[list[Issue]], None]
    human_decisions: list[HumanDecision]   # injected before each cycle — Builder reads as ground truth
```

`LoopContext` in `research_loop.py` also extends `BaseContext` — replacing its current 4 duplicated fields.

---

## 5. `ConvergeStrategy`

**Standalone class — does NOT extend `Strategy` and is NOT registered in `_STRATEGY_REGISTRY`.** Lives in `src/document_strategy.py`. Used exclusively by `DocumentRefiner`, which instantiates it directly. The research loop and strategy factory are uninvolved. The `converge` value in the YAML `execution.strategy` field is handled by the CLI routing to `DocumentRefiner` — it never reaches `get_strategy()`.

```python
class ConvergeStrategy:
    """Standalone strategy for document convergence. Not a Strategy subclass."""

    def run_builder(self, prd: str, patches: list[Patch], invoke) -> str:
        # Cycle 1: generate initial PRD from source material
        # Cycle N: verify each patch before applying, reject stale patches with reason
        ...

    def run_challenger(self, prd: str, invoke) -> list[RawCritique]:
        # Internal consistency review
        # Each critique must include: section_ref, description, proposed resolution
        ...

    def run_personas(self, prd: str, invoke) -> list[RawCritique]:
        # Parallel or serial per strategy_config.persona_mode
        # Each persona uses prd_persona_{name}.md failure model prompt
        ...

    def run_verifier(self, prd: str, critiques: list[RawCritique], invoke) -> list[VerifiedCritique]:
        # Utility backend reads PRD at each section_ref
        # Classifies: VALID | STALE | DEFER(out_of_scope) | DEFER(needs_research) | DEFER(human_required)
        # For human_required: also produces HumanInputRequest with question + suggested_answer
        # Does NOT generate patches — classification only
        ...

    def run_arbitrator(self, prd: str, critiques: list[VerifiedCritique], invoke) -> list[Patch]:
        # Judge backend
        # Generates one patch proposal per VALID critique
        # patch: {issue_id, section_ref, proposed_text, rationale}
        ...
```

### 5.1 Persona execution modes

**Parallel:** all persona backends run concurrently via `ThreadPoolExecutor` (same pattern as `EnsembleStrategy`). Each persona sees the same PRD snapshot. Results are merged before the Verifier step.

**Serial:** personas run sequentially. Each persona sees the PRD but NOT the previous persona's critique — prevents cross-contamination of failure models. Results concatenated before the Verifier step.

### 5.2 Backend role convention for `ConvergeStrategy`

| Role | BackendsConfig field | Fallback |
|---|---|---|
| Builder | `research[0]` | `primary` |
| Challenger | `research[1]` | `primary` |
| Personas | `primary` (all persona calls use the same backend; identity comes from the prompt) | — |
| Verifier | `utility` | `primary` |
| Arbitrator | `judge` | `primary` |

### 5.3 Persona routing

Each persona name maps to a prompt file: `prompts/prd_persona_{name}.md`. Adding a custom persona requires only a new prompt file + YAML entry. No code change.

---

## 6. Config Extensions

### 6.1 New dataclasses in `config.py`

`DocumentConfig` is a top-level config loaded independently by the `refine` CLI subcommand. It does NOT extend or nest inside `ResearchConfig` — research-mode fields (`dimensions`, `scoring`, `evaluation`, `methodology`) are irrelevant to document runs and must not bleed through.

```python
@dataclass(frozen=True)
class PersonaConfig:
    name: str
    prompt_file: str = ""    # defaults to prompts/prd_persona_{name}.md

@dataclass(frozen=True)
class ArtifactConfig:
    name: str                  # output filename, e.g. "V1_ALPHA_VERTICAL_SLICE.md"
    layer: str                 # "execution" | "companion"
    prompt_file: str = ""      # defaults to prompts/artifact_{stem}.md ({stem} = name without .md)
    review: bool = True        # if True: one Challenger + Persona + Verifier pass before finalizing

@dataclass(frozen=True)
class DocumentConfig:
    topic: str                          # what the primary artifact is about
    goal: str                           # desired deliverable description
    primary_artifact: str = "PRD.md"   # filename of the primary convergence target
    source_material: str = ""           # initial context fed to Builder on cycle 1
    convergence_cycles: int = 1
    max_cycles: int = 0
    persona_mode: str = "parallel"      # "parallel" | "serial"
    personas: tuple[PersonaConfig, ...] = (
        PersonaConfig("architect"),
        PersonaConfig("scrum_master"),
        PersonaConfig("product_owner"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> DocumentConfig: ...
```

### 6.2 Example YAML

`document:` is a top-level key — not nested under `research:`. The `refine` subcommand loads it directly into `DocumentConfig`. No `dimensions`, `scoring`, or `evaluation` keys appear.

```yaml
document:
  topic: "Iris — engineering intelligence platform PRD"
  goal: "Produce an execution-ready product requirements document"
  primary_artifact: PRD.md
  source_material: "path/to/raw_notes.md"
  convergence_cycles: 1
  max_cycles: 0
  persona_mode: parallel
  personas:
    - name: architect
    - name: scrum_master
    - name: product_owner
  artifacts:
      # execution artifacts
      - name: V1_ALPHA_VERTICAL_SLICE.md
        layer: execution
        review: true
      - name: ACCEPTANCE_CRITERIA_V1.md
        layer: execution
        review: true
      - name: PLATFORM_DECISIONS_REQUIRED.md
        layer: execution
        review: false
      - name: EPICS_AND_MILESTONES.md
        layer: execution
        review: true
      - name: MANAGER_AHA_MOMENT.md
        layer: execution
        review: false
      # companion specs — generated flat at root, no subfolder
      - name: CORPUS_ARCHITECTURE.md
        layer: companion
        review: false
      - name: REVIEWER_EXPERIENCE_PRINCIPLES.md
        layer: companion
        review: true
      - name: ONBOARDING_NARRATIVE_DAY1_DAY7_DAY30.md
        layer: companion
        review: false

  backends:
    primary: codex            # Builder (research[0])
    research: [codex, claude] # research[0]=Builder, research[1]=Challenger
    judge: gemini             # Arbitrator
    utility: claude           # Verifier
  strategy_config:
    critique_depth: thorough
```

---

## 7. Output Artifacts

The run produces a clean, flat document package. All files land at the run root — no agent-named subdirectories (`CODEX/`, `COPILOT/`), no archive folder. Only structured output.

### 7.1 Document package (user-facing)

```
output/my-prd-run/
├── PRD.md                              # canonical (converged)
│
│   # execution artifacts (layer: execution)
├── V1_ALPHA_VERTICAL_SLICE.md
├── ACCEPTANCE_CRITERIA_V1.md
├── PLATFORM_DECISIONS_REQUIRED.md
├── MINIMUM_CREDIBLE_INSIGHT_STANDARD.md
├── ONBOARDING_AND_COLD_START_STRATEGY.md
├── EPICS_AND_MILESTONES.md
├── IA_AND_KEY_SCREENS.md
├── REVIEW_QUEUE_SPEC.md
├── MANAGER_AHA_MOMENT.md
│
│   # companion specs (layer: companion) — flat, no subfolder
├── CORPUS_ARCHITECTURE.md
├── REVIEWER_EXPERIENCE_PRINCIPLES.md
├── ONBOARDING_NARRATIVE_DAY1_DAY7_DAY30.md
│
│   # auto-generated
├── DOCS_INDEX.md
└── README.md
```

All artifact names, layers, and review flags are **declared in the YAML** (see Section 6.2). The list above reflects the Iris session output. Archive files (draft PRD history) are never generated — they belong in `.run/` as audit trail only.

**Artifact prompt convention:** each artifact's generation prompt lives at `prompts/artifact_{stem}.md` where `{stem}` is the artifact filename without `.md` (e.g. `prompts/artifact_V1_ALPHA_VERTICAL_SLICE.md`). The Builder receives: the converged primary artifact, the artifact's prompt, and any already-generated artifacts of `layer: companion` as additional context. A custom `prompt_file` in `ArtifactConfig` overrides the default path.

### 7.2 Run artifacts (machine-readable)

```
output/my-prd-run/.run/
├── PRD_v1.md, PRD_v2.md...   # one PRD snapshot per cycle (audit trail)
├── issue_registry.json       # full Issue log with lifecycle state
├── critiques_N.json          # raw critiques per cycle (Challenger + Personas)
├── patches_N.json            # patch proposals from Arbitrator per cycle
├── cycles/
│   └── cycle_001.md          # narrative: what was critiqued, what was patched
├── results.tsv               # cycle log: valid_critiques, stale, deferred, patches_applied
├── metrics.json
├── run_manifest.json
└── report.html
```

Run artifacts live in `.run/` to keep the document package clean. `issue_registry.json` is the single audit trail — every critique raised, its verification outcome, and whether a patch was applied.

```
output/my-prd-run/.run/
├── ...
├── pending_questions.json    # written when human_required deferrals exist — overwritten each cycle
└── human_decisions.json      # append-only — full audit trail of every human decision across cycles
```

`pending_questions.json` is overwritten each time new `human_required` questions arise. `human_decisions.json` is append-only — it persists across `--resume` invocations and is the audit trail for all human input.

### 7.3 Workflow phases

The run executes in three sequential phases:

| Phase | What happens | Output |
|---|---|---|
| **1 — Convergence** | PRD.md refined through adversarial cycles until clean | `PRD.md` (converged) |
| **2 — Expansion** | Execution artifacts generated from the converged PRD, each optionally reviewed | Named execution artifacts |
| **3 — Indexing** | `DOCS_INDEX.md` and `README.md` auto-generated from the declared package | `DOCS_INDEX.md`, `README.md` |

Execution artifacts declared with `review: true` in the YAML go through one Challenger + Persona + Verifier pass before being written as final. Artifacts declared with `review: false` are generated directly from the converged PRD by the Builder and written immediately.

**Phase 3 prompts — always run, not configurable:**

| Prompt | Inputs | Output |
|---|---|---|
| `prompts/generate_readme.md` | artifact manifest (names + layers), `topic`, `goal`, `primary_artifact` name | `README.md` — entry point with quick-start links by audience |
| `prompts/generate_docs_index.md` | full artifact manifest with layers + review flags, personas list, PRD section summary (§1 Executive Summary + §2 Problem Statement) | `DOCS_INDEX.md` — audience-based reading orders with time estimates, status table, archive description |

Phase 3 always regenerates both files from final artifact state. The Builder backend runs both calls.

---

## 8. Convergence Logic

```python
def _should_stop(state: CycleState, config: DocumentConfig) -> bool:
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles

def _update_convergence(state: CycleState, valid_count: int, human_required_count: int) -> None:
    if valid_count == 0 and human_required_count == 0:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0
```

A cycle is clean only when: **zero VALID critiques AND zero `human_required` deferrals.**

`DEFER(out_of_scope)` and `DEFER(needs_research)` do NOT reset the counter — they are non-blocking. Only unresolved human questions block convergence. This means a run with good source material and no ambiguous decisions can converge without any human interaction at all.

---

## 9. CLI and Human-in-the-Loop

### 9.1 Commands

```bash
# Research mode (unchanged)
auto-research run --config configs/my_topic.yaml

# Document mode
auto-research refine --config configs/my_prd.yaml                    # interactive (default)
auto-research refine --config configs/my_prd.yaml --no-interactive   # async/CI mode
auto-research refine --config configs/my_prd.yaml --resume           # continue after answering
```

The CLI routes to `DocumentRefiner` when the config contains a top-level `document:` key. Both subcommands share the same config loading path.

### 9.2 Interactive mode (default)

When `human_required` deferrals are found, the cycle pauses and the terminal prompts the operator. The Verifier's `suggested_answer` is shown — operator hits Enter to confirm or types an override:

```
[refine] Cycle 2 — 2 questions require your input before proceeding.

──────────────────────────────────────
Question 1 of 2  [I-04]
──────────────────────────────────────
Context: §15.1 Open Questions — Regulated account topology
Issue: "The document states regulated tenants require dedicated
        infrastructure but does not specify whether example-org and
        casa-de-bolsa share one AWS account or have separate accounts."

Suggested answer: "One account per regulated tenant (maximum isolation)"

Press Enter to accept, or type your answer:
> each bank gets its own account — legal confirmed this

──────────────────────────────────────
Question 2 of 2  [I-07]
──────────────────────────────────────
...

[refine] Answers recorded. Resuming cycle 2.
```

### 9.3 Async mode (`--no-interactive`)

For CI pipelines or unattended runs. When `human_required` deferrals are found:

1. Writes `.run/pending_questions.json` with all `HumanInputRequest` records
2. Prints a summary of what is blocked
3. Exits with a non-zero code

Operator fills in the `answer` field per question in `pending_questions.json`, then re-runs with `--resume`. Answers are loaded from `human_decisions.json`, injected into `CycleContext`, and the cycle continues.

### 9.4 How answers feed back into the document

Human decisions are injected into every subsequent Builder call as a ground-truth block **before** the PRD content. The Builder rewrites the relevant sections using the answer as a constraint — decisions propagate through the normal patch cycle, not as direct text injection:

```
--- HUMAN DECISIONS (ground truth — do not contradict) ---

[I-04] Regulated account topology:
  Answer: Each regulated tenant (example-org, casa-de-bolsa) gets its own
          dedicated AWS account. This is a legal/compliance requirement.

[I-07] Jira auth for on-premise tenants:
  Answer: API token only — no OAuth for Jira Data Center deployments.

---
```

### 9.5 What HITL is NOT

- Not a free-form chat — questions are structured, scoped, Verifier-generated
- Not a bypass of the adversarial cycle — human answers become source-of-truth constraints that still go through the Builder → Challenger → Verifier pipeline
- Not mandatory — if source material is complete, `human_required` deferrals should be zero and the run converges without human interaction

---

## 10. Testing Strategy

- `tests/test_document_loop.py` — unit tests for `run_cycle()`, convergence logic (`valid=0,human=0` → clean; `human>0` → not clean), issue registry updates, HITL pause/resume flow.
- `tests/test_document_refiner.py` — integration tests for setup, teardown, artifact writing, Phase 2 expansion, Phase 3 indexing, `--no-interactive` exit behavior.
- `tests/test_document_strategy.py` — unit tests for `ConvergeStrategy` (all 5 methods), backend role resolution, persona parallel/serial execution, `run_verifier` DEFER reason classification.
- `tests/test_strategy.py` — untouched. `ConvergeStrategy` is not a `Strategy` subclass and requires no changes here.
- Existing test suite untouched — research mode has zero regression risk.

---

## 11. Out of scope (v1)

- Cross-document consistency checks (same concept with different values across multiple execution artifacts)
- Scope inflation warnings (Must-Have count tracking per cycle)
- Portfolio support for document runs
- Diagrams generation (`.mmd` / `.png` — the Iris session produced these manually)
- Agent-named subdirectories (`CODEX/`, `COPILOT/`) — all artifacts generate flat at root
- Archive folder — draft PRD history lives in `.run/` as audit trail, never in the output package
- Per-artifact adversarial convergence (Phase 2 artifacts get at most one review pass in v1, not a full cycle loop)

These belong in v2.
