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
│   └── strategy.py            # ConvergeStrategy added
│
├── prompts/
│   ├── prd_builder.md
│   ├── prd_challenger.md
│   ├── prd_verify.md
│   ├── prd_arbitrate.md
│   ├── prd_persona_architect.md
│   ├── prd_persona_scrum_master.md
│   └── prd_persona_product_owner.md
│
├── configs/
│   └── prd_template.yaml
│
└── tests/
    ├── test_document_loop.py
    └── test_document_refiner.py
```

### 2.2 Unchanged files

`orchestrator.py`, `research_loop.py`, `run_state.py`, `scorer.py` — untouched. All existing research configs and the `run` CLI subcommand continue to work as before.

### 2.3 Modified files

| File | Change |
|---|---|
| `src/config.py` | Add `PersonaConfig`, `DocumentConfig`, `document` field on `ResearchConfig` |
| `src/strategy.py` | Add `ConvergeStrategy`, register in `_STRATEGY_REGISTRY` |
| `src/cli.py` | Add `refine` subcommand, route to `DocumentRefiner` when `strategy: converge` |

---

## 3. Cycle Execution

Each document cycle runs five steps in sequence:

```
Builder          → produces PRD.md (cycle 1) or applies validated patches (cycle N+)
Challenger       → internal consistency critique with mandatory section references
Personas         → stakeholder critique (parallel or serial per config)
Verifier         → reads PRD.md at each referenced section → VALID / STALE / DEFER
Arbitrator       → generates patch proposals for VALID critiques only
Builder          → applies patches, writes new PRD.md version
Issue registry   → updated with lifecycle state per critique
Convergence check → clean cycle? increment counter. any VALID critique? reset to 0.
```

**Termination:** when `consecutive_clean_cycles >= config.document.convergence_cycles` (default: 1). Also terminates on `max_cycles` if set.

---

## 4. Data Model

### 4.1 `CycleState`

```python
@dataclass
class CycleState:
    prd: str = ""
    prd_path: Path = Path("PRD.md")
    prd_versions: list[str] = field(default_factory=list)
    cycle: int = 0
    issue_registry: list[Issue] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    results_path: Path = Path("results.tsv")
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
    verified_cycle: int | None = None
    patch_applied: bool = False
```

### 4.3 `CycleContext`

Mirrors `LoopContext`. Carries:
- `call_with`, `invoke_for_strategy`, `track_usage`, `track_cost` — shared with research mode
- `read_prd_section(ref: str) -> str` — reads current PRD at the referenced section
- `update_issue_registry(issues: list[Issue]) -> None`

---

## 5. `ConvergeStrategy`

Extends `Strategy`. Adds five dedicated methods called by `document_loop.run_cycle()`:

```python
class ConvergeStrategy(Strategy):
    name = "converge"

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
        # Classifies: VALID / STALE / DEFER
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

```python
@dataclass(frozen=True)
class PersonaConfig:
    name: str
    prompt_file: str = ""    # defaults to prd_persona_{name}.md

@dataclass(frozen=True)
class ArtifactConfig:
    name: str                  # filename, e.g. "V1_ALPHA_VERTICAL_SLICE.md"
    layer: str                 # "execution" | "companion"
    prompt_file: str = ""      # defaults to artifact_{name}.md (without .md extension)
    review: bool = True        # if True: Challenger + Persona + Verifier pass before finalizing

@dataclass(frozen=True)
class DocumentConfig:
    source_material: str = ""
    convergence_cycles: int = 1
    max_cycles: int = 0
    persona_mode: str = "parallel"    # "parallel" | "serial"
    personas: tuple[PersonaConfig, ...] = (
        PersonaConfig("architect"),
        PersonaConfig("scrum_master"),
        PersonaConfig("product_owner"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()   # execution/companion docs to generate after PRD converges
```

`ResearchConfig` gains: `document: DocumentConfig = field(default_factory=DocumentConfig)`

### 6.2 Example YAML

```yaml
research:
  topic: "Iris — engineering intelligence platform PRD"
  goal: "Produce an execution-ready product requirements document"
  dimensions:
    - scope discipline
    - release framing
    - use case prioritization
    - acceptance criteria coverage
    - internal consistency

  document:
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

  execution:
    strategy: converge
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

All artifact names, layers, and review flags are **declared in the YAML** (see Section 6.3). The list above reflects the Iris session output. Archive files (draft PRD history) are never generated — they belong in `.run/` as audit trail only.

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

### 7.3 Workflow phases

The run executes in three sequential phases:

| Phase | What happens | Output |
|---|---|---|
| **1 — Convergence** | PRD.md refined through adversarial cycles until clean | `PRD.md` (converged) |
| **2 — Expansion** | Execution artifacts generated from the converged PRD, each optionally reviewed | Named execution artifacts |
| **3 — Indexing** | `DOCS_INDEX.md` and `README.md` auto-generated from the declared package | `DOCS_INDEX.md`, `README.md` |

Execution artifacts declared with `review: true` in the YAML go through one Challenger + Persona + Verifier pass before being written as final. Artifacts declared with `review: false` are generated directly from the PRD by the Builder and written immediately.

---

## 8. Convergence Logic

```python
def _should_stop(state: CycleState, config: DocumentConfig) -> bool:
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles

def _update_convergence(state: CycleState, valid_critique_count: int) -> None:
    if valid_critique_count == 0:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0
```

A cycle is clean when the Verifier returns zero VALID critiques. STALE and DEFER do not reset the counter.

---

## 9. CLI

```bash
# Research mode (unchanged)
auto-research run --config configs/my_topic.yaml

# Document mode (new)
auto-research refine --config configs/my_prd.yaml
auto-research refine --config configs/my_prd.yaml --resume
```

The CLI routes to `DocumentRefiner` when `strategy: converge` is set. Both subcommands share the same config loading path.

---

## 10. Testing Strategy

- `tests/test_document_loop.py` — unit tests for `run_cycle()`, convergence logic, issue registry updates. Uses JSONL backend (no real LLM calls).
- `tests/test_document_refiner.py` — integration tests for setup, teardown, artifact writing.
- `tests/test_strategy.py` — extended with `ConvergeStrategy` cases.
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
