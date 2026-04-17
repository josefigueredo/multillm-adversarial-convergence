# Document Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `DocumentRefiner` class and `refine` CLI subcommand to auto-research that runs a multi-LLM adversarial convergence loop to produce structured document packages (PRDs + execution artifacts).

**Architecture:** `DocumentRefiner` is a sibling class to `AutoResearcher` — it shares backends, config loading patterns, and reporting infrastructure but runs a completely different loop (converge, not accumulate). `ConvergeStrategy` is a standalone class (NOT a `Strategy` subclass, NOT in `_STRATEGY_REGISTRY`) that orchestrates the five-step Builder → Challenger → Personas → Verifier → Arbitrator cycle. All new state types (`Issue`, `CycleState`, `CycleContext`) live in `document_loop.py`; shared callback infrastructure (`BaseContext`) is extracted from `research_loop.py` into `run_state.py`.

**Tech Stack:** Python 3.12, dataclasses, `concurrent.futures.ThreadPoolExecutor` (parallel persona execution), `json`, `yaml`, existing `Backend` / `AgentResponse` / `CallOptions` types from `src/backends/`.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `src/config.py` | Add `PersonaConfig`, `ArtifactConfig`, `DocumentConfig` with `from_yaml` |
| Create | `src/hitl.py` | `DeferReason`, `HumanInputRequest`, `HumanDecision`, interactive + async collection |
| Modify | `src/run_state.py` | Add `BaseContext` dataclass (4 shared callbacks) |
| Modify | `src/research_loop.py` | `LoopContext` extends `BaseContext` (removes 4 duplicate fields) |
| Create | `src/document_loop.py` | `Issue`, `CycleState`, `CycleContext`, `run_cycle()`, convergence helpers |
| Create | `src/document_strategy.py` | `RawCritique`, `VerifiedCritique`, `Patch`, `ConvergeStrategy` |
| Create | `src/document_refiner.py` | `DocumentRefiner` — Phase 1 convergence, Phase 2 expansion, Phase 3 indexing |
| Modify | `src/cli.py` | Add `refine` subcommand, `--no-interactive`, `--resume` flags |
| Create | `prompts/prd_builder.md` | Builder prompt — generate or patch primary artifact |
| Create | `prompts/prd_challenger.md` | Challenger prompt — internal consistency critique |
| Create | `prompts/prd_verify.md` | Verifier prompt — classify critiques VALID/STALE/DEFER |
| Create | `prompts/prd_arbitrate.md` | Arbitrator prompt — generate patch proposals |
| Create | `prompts/prd_persona_architect.md` | Cloud architect failure-model persona |
| Create | `prompts/prd_persona_scrum_master.md` | Scrum master failure-model persona |
| Create | `prompts/prd_persona_product_owner.md` | Product owner failure-model persona |
| Create | `prompts/generate_readme.md` | Phase 3 — generate README.md from artifact manifest |
| Create | `prompts/generate_docs_index.md` | Phase 3 — generate DOCS_INDEX.md from artifact manifest |
| Create | `configs/prd_template.yaml` | Template YAML for a document run |
| Create | `tests/test_document_config.py` | DocumentConfig loading tests |
| Create | `tests/test_hitl.py` | HITL collection and persistence tests |
| Create | `tests/test_document_loop.py` | CycleState, Issue, convergence logic, run_cycle tests |
| Create | `tests/test_document_strategy.py` | ConvergeStrategy — backend resolution, all 5 methods |
| Create | `tests/test_document_refiner.py` | DocumentRefiner — phase execution, file output, CLI integration |

---

## Task 1: DocumentConfig in config.py

**Files:**
- Modify: `src/config.py` (append after `ResearchConfig`)
- Create: `tests/test_document_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_document_config.py
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from src.config import DocumentConfig, PersonaConfig, ArtifactConfig


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_document_config_minimal(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "My PRD"
          goal: "Build it"
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.topic == "My PRD"
    assert cfg.goal == "Build it"
    assert cfg.primary_artifact == "PRD.md"
    assert cfg.convergence_cycles == 1
    assert cfg.max_cycles == 0
    assert cfg.persona_mode == "parallel"
    assert len(cfg.personas) == 3


def test_document_config_full(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "Iris PRD"
          goal: "Execution-ready PRD"
          primary_artifact: "SPEC.md"
          convergence_cycles: 2
          max_cycles: 10
          persona_mode: serial
          personas:
            - name: architect
            - name: product_owner
          artifacts:
            - name: V1_SLICE.md
              layer: execution
              review: true
            - name: ARCH.md
              layer: companion
              review: false
          backends:
            primary: claude
            research: [codex, claude]
            judge: gemini
            utility: claude
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.primary_artifact == "SPEC.md"
    assert cfg.convergence_cycles == 2
    assert cfg.max_cycles == 10
    assert cfg.persona_mode == "serial"
    assert len(cfg.personas) == 2
    assert cfg.personas[0].name == "architect"
    assert len(cfg.artifacts) == 2
    assert cfg.artifacts[0].layer == "execution"
    assert cfg.artifacts[1].review is False
    assert cfg.backends.primary == "claude"
    assert cfg.backends.research == ("codex", "claude")
    assert cfg.backends.judge == "gemini"


def test_document_config_missing_topic_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          goal: "No topic"
    """)
    with pytest.raises(ValueError, match="topic"):
        DocumentConfig.from_yaml(cfg_path)


def test_document_config_missing_document_key_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        research:
          topic: "Wrong key"
          goal: "x"
          dimensions: []
    """)
    with pytest.raises(ValueError, match="document"):
        DocumentConfig.from_yaml(cfg_path)


def test_document_config_invalid_persona_mode_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          persona_mode: diagonal
    """)
    with pytest.raises(ValueError, match="persona_mode"):
        DocumentConfig.from_yaml(cfg_path)


def test_persona_config_default_prompt_file():
    p = PersonaConfig(name="architect")
    assert p.prompt_file == ""


def test_artifact_config_defaults():
    a = ArtifactConfig(name="V1.md", layer="execution")
    assert a.review is True
    assert a.prompt_file == ""
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/josefigueredo/Code/josefigueredo/auto-research
pytest tests/test_document_config.py -v 2>&1 | head -30
```
Expected: `ImportError` or `AttributeError` — `PersonaConfig`, `ArtifactConfig`, `DocumentConfig` not yet defined.

- [ ] **Step 3: Implement in config.py**

Append at the end of `src/config.py`, after `ResearchConfig`:

```python
# ---------------------------------------------------------------------------
# Document-mode configuration (loaded by `refine` subcommand)
# ---------------------------------------------------------------------------

VALID_PERSONA_MODES = ("parallel", "serial")


@dataclass(frozen=True)
class PersonaConfig:
    """A single reviewer persona for the document convergence loop.

    Attributes:
        name: Short identifier (e.g. ``"architect"``). Maps to
            ``prompts/prd_persona_{name}.md`` by default.
        prompt_file: Override path for the persona prompt. Empty string
            means use the default mapping.
    """

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class ArtifactConfig:
    """A secondary artifact generated in Phase 2 (Expansion).

    Attributes:
        name: Output filename (e.g. ``"V1_ALPHA_VERTICAL_SLICE.md"``).
        layer: ``"execution"`` or ``"companion"``.
        prompt_file: Override prompt path. Defaults to
            ``prompts/artifact_{stem}.md``.
        review: If ``True``, one Challenger + Persona + Verifier pass
            runs before writing the final file.
    """

    name: str
    layer: str
    prompt_file: str = ""
    review: bool = True


@dataclass(frozen=True)
class DocumentConfig:
    """Top-level configuration for a document refinement run.

    Loaded by ``DocumentConfig.from_yaml`` from a YAML file that contains
    a top-level ``document:`` key.  Independent of ``ResearchConfig``.
    """

    topic: str
    goal: str
    primary_artifact: str = "PRD.md"
    source_material: str = ""
    convergence_cycles: int = 1
    max_cycles: int = 0
    persona_mode: str = "parallel"
    personas: tuple[PersonaConfig, ...] = (
        PersonaConfig("architect"),
        PersonaConfig("scrum_master"),
        PersonaConfig("product_owner"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "DocumentConfig":
        """Load a document config from a YAML file.

        The YAML must contain a top-level ``document:`` key with at least
        ``topic`` and ``goal`` fields.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is malformed or missing required fields.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        if "document" not in raw:
            raise ValueError("Config must contain a top-level 'document' key")

        doc: dict[str, Any] = raw["document"]

        if "topic" not in doc:
            raise ValueError("'document' section must contain a 'topic' field")

        persona_mode = doc.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        personas = tuple(
            PersonaConfig(
                name=p["name"],
                prompt_file=p.get("prompt_file", ""),
            )
            for p in doc.get("personas", [])
        ) or (
            PersonaConfig("architect"),
            PersonaConfig("scrum_master"),
            PersonaConfig("product_owner"),
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in doc.get("artifacts", [])
        )

        backends_raw: dict[str, Any] = doc.get("backends", {})
        if backends_raw:
            research_val = backends_raw.get("research", [backends_raw.get("primary", "claude")])
            if isinstance(research_val, str):
                research_val = [research_val]
            backends_cfg = BackendsConfig(
                primary=backends_raw.get("primary", "claude"),
                research=tuple(research_val),
                judge=backends_raw.get("judge", ""),
                utility=backends_raw.get("utility", ""),
            )
        else:
            backends_cfg = BackendsConfig()

        strat_raw: dict[str, Any] = doc.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )

        return cls(
            topic=doc["topic"],
            goal=doc.get("goal", doc["topic"]),
            primary_artifact=doc.get("primary_artifact", "PRD.md"),
            source_material=doc.get("source_material", ""),
            convergence_cycles=doc.get("convergence_cycles", 1),
            max_cycles=doc.get("max_cycles", 0),
            persona_mode=persona_mode,
            personas=personas,
            artifacts=artifacts,
            backends=backends_cfg,
            strategy_config=strategy_cfg,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_document_config.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_document_config.py
git commit -m "feat(config): add PersonaConfig, ArtifactConfig, DocumentConfig"
```

---

## Task 2: HITL module

**Files:**
- Create: `src/hitl.py`
- Create: `tests/test_hitl.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hitl.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from src.hitl import (
    DeferReason,
    HumanDecision,
    HumanInputRequest,
    collect_interactive,
    load_human_decisions,
    write_pending_questions,
)


def _req(issue_id: str = "I-01") -> HumanInputRequest:
    return HumanInputRequest(
        issue_id=issue_id,
        question="Which deployment model?",
        context="§5.1 — account topology",
        suggested_answer="One account per tenant",
        cycle=1,
    )


def test_collect_interactive_accepts_suggestion(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    decisions = collect_interactive([_req()])
    assert len(decisions) == 1
    assert decisions[0].answer == "One account per tenant"
    assert decisions[0].answered_by == "auto-confirmed"
    assert decisions[0].issue_id == "I-01"


def test_collect_interactive_overrides_answer(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "custom answer")
    decisions = collect_interactive([_req()])
    assert decisions[0].answer == "custom answer"
    assert decisions[0].answered_by == "human"


def test_collect_interactive_multiple(monkeypatch):
    answers = iter(["", "my answer"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    decisions = collect_interactive([_req("I-01"), _req("I-02")])
    assert len(decisions) == 2
    assert decisions[0].answered_by == "auto-confirmed"
    assert decisions[1].answered_by == "human"


def test_write_pending_questions(tmp_path):
    req = _req()
    write_pending_questions([req], tmp_path / "pending.json")
    data = json.loads((tmp_path / "pending.json").read_text())
    assert isinstance(data, list)
    assert data[0]["issue_id"] == "I-01"
    assert data[0]["question"] == "Which deployment model?"
    assert data[0]["suggested_answer"] == "One account per tenant"


def test_load_human_decisions_returns_empty_when_missing(tmp_path):
    decisions = load_human_decisions(tmp_path / "nonexistent.json")
    assert decisions == []


def test_load_human_decisions_reads_existing(tmp_path):
    p = tmp_path / "decisions.json"
    p.write_text(json.dumps([
        {
            "issue_id": "I-01",
            "question": "Q?",
            "answer": "A",
            "answered_at": "2026-04-17T10:00:00+00:00",
            "answered_by": "human",
        }
    ]))
    decisions = load_human_decisions(p)
    assert len(decisions) == 1
    assert decisions[0].issue_id == "I-01"
    assert decisions[0].answer == "A"


def test_defer_reason_constants():
    assert DeferReason.OUT_OF_SCOPE == "out_of_scope"
    assert DeferReason.NEEDS_RESEARCH == "needs_research"
    assert DeferReason.HUMAN_REQUIRED == "human_required"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_hitl.py -v 2>&1 | head -20
```
Expected: `ImportError` — `src/hitl.py` does not exist.

- [ ] **Step 3: Implement src/hitl.py**

```python
# src/hitl.py
"""Human-in-the-loop data structures and collection helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


class DeferReason:
    OUT_OF_SCOPE = "out_of_scope"
    NEEDS_RESEARCH = "needs_research"
    HUMAN_REQUIRED = "human_required"


@dataclass
class HumanInputRequest:
    """A question the Verifier could not resolve from the document alone."""

    issue_id: str
    question: str
    context: str
    suggested_answer: str
    cycle: int


@dataclass
class HumanDecision:
    """A resolved human answer for a deferred issue."""

    issue_id: str
    question: str
    answer: str
    answered_at: str
    answered_by: str  # "human" | "auto-confirmed"


def collect_interactive(requests: list[HumanInputRequest]) -> list[HumanDecision]:
    """Prompt the operator for each pending question and collect answers.

    Pressing Enter accepts the Verifier's suggested_answer (answered_by=
    'auto-confirmed'). Typing a non-empty string overrides it
    (answered_by='human').
    """
    decisions: list[HumanDecision] = []
    total = len(requests)
    print(f"\n[refine] {total} question(s) require your input before proceeding.\n")
    for i, req in enumerate(requests, 1):
        print(f"{'─' * 50}")
        print(f"Question {i} of {total}  [{req.issue_id}]")
        print(f"{'─' * 50}")
        print(f"Context: {req.context}")
        print(f"Issue: {req.question}\n")
        print(f"Suggested answer: {req.suggested_answer}\n")
        raw = input("Press Enter to accept, or type your answer: ").strip()
        if raw:
            answer = raw
            answered_by = "human"
        else:
            answer = req.suggested_answer
            answered_by = "auto-confirmed"
        decisions.append(HumanDecision(
            issue_id=req.issue_id,
            question=req.question,
            answer=answer,
            answered_at=datetime.now(timezone.utc).isoformat(),
            answered_by=answered_by,
        ))
    print("\n[refine] Answers recorded. Resuming.\n")
    return decisions


def write_pending_questions(requests: list[HumanInputRequest], path: Path) -> None:
    """Write pending questions to JSON for async / CI mode."""
    path.write_text(
        json.dumps([asdict(r) for r in requests], indent=2),
        encoding="utf-8",
    )


def load_human_decisions(path: Path) -> list[HumanDecision]:
    """Load human decisions from a JSON file. Returns [] if file is missing."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [HumanDecision(**item) for item in raw]


def append_human_decisions(decisions: list[HumanDecision], path: Path) -> None:
    """Append decisions to the audit-trail JSON file (creates if missing)."""
    existing = load_human_decisions(path)
    existing.extend(decisions)
    path.write_text(
        json.dumps([asdict(d) for d in existing], indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_hitl.py -v
```
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/hitl.py tests/test_hitl.py
git commit -m "feat(hitl): add DeferReason, HumanInputRequest, HumanDecision, collection helpers"
```

---

## Task 3: BaseContext extraction

Extract 4 shared callbacks from `LoopContext` into `BaseContext` in `run_state.py`. `LoopContext` then extends `BaseContext` (removing the 4 duplicate fields).

**Files:**
- Modify: `src/run_state.py` (add `BaseContext`)
- Modify: `src/research_loop.py` (`LoopContext` extends `BaseContext`)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_run_state.py (append after existing tests)
from src.run_state import BaseContext
from src.research_loop import LoopContext
from src.backends import AgentResponse


def test_base_context_is_dataclass():
    import dataclasses
    assert dataclasses.is_dataclass(BaseContext)


def test_loop_context_is_subclass_of_base_context():
    assert issubclass(LoopContext, BaseContext)


def test_base_context_has_four_callbacks():
    import inspect
    fields = {f.name for f in dataclasses.fields(BaseContext)}
    assert fields == {"call_with", "invoke_for_strategy", "track_usage", "track_cost"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_run_state.py -v -k "base_context or loop_context_is_subclass" 2>&1 | tail -15
```
Expected: `ImportError` — `BaseContext` not in `run_state`.

- [ ] **Step 3: Add BaseContext to run_state.py**

Append at the top of `src/run_state.py` (after the imports, before `UsageTotals`):

```python
from typing import Callable

from .backends import AgentResponse


@dataclass
class BaseContext:
    """Shared callback bundle for research and document loops.

    Both ``LoopContext`` (research mode) and ``CycleContext`` (document mode)
    extend this class. When orchestrator callback signatures change, only
    ``BaseContext`` needs updating.
    """

    call_with: Callable[..., AgentResponse]
    invoke_for_strategy: Callable[..., AgentResponse]
    track_usage: Callable[[AgentResponse, str], None]
    track_cost: Callable[[float, str], None]
```

Note: `run_state.py` already imports `from .backends import AgentResponse` — add `Callable` to the `from typing import` line and add `from dataclasses import dataclass` if not already present (check first — it imports `dataclass, field`).

- [ ] **Step 4: Update LoopContext in research_loop.py**

Find `LoopContext` in `src/research_loop.py` (lines 36-55) and replace with:

```python
from .run_state import BaseContext  # add to imports at top of file


@dataclass
class LoopContext(BaseContext):
    """Immutable bundle of callbacks and config for the research loop.

    Extends ``BaseContext`` which provides: ``call_with``,
    ``invoke_for_strategy``, ``track_usage``, ``track_cost``.
    """

    config: ResearchConfig
    strategy: Any
    track_candidate_usage: Callable[[ResearchCandidate], None]
    collect_provenance: Callable[..., None]
    methodology_summary: Callable[[], str]
    kb_summary: Callable[[], str]
    format_dimension_list: Callable[[list[str]], str]
    goal_constraints_summary: Callable[[], str]
```

The 4 fields (`call_with`, `invoke_for_strategy`, `track_usage`, `track_cost`) are removed from `LoopContext` — they now come from `BaseContext`. All existing construction of `LoopContext` uses keyword args so the field order change is safe.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests PASS. The new base context tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/run_state.py src/research_loop.py tests/test_run_state.py
git commit -m "refactor(run_state): extract BaseContext from LoopContext"
```

---

## Task 4: Document data model

**Files:**
- Create: `src/document_loop.py` (data structures only — functions added in Task 6)
- Create: `tests/test_document_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_document_loop.py
from __future__ import annotations
import dataclasses
from pathlib import Path
import pytest
from src.document_loop import (
    CycleContext,
    CycleState,
    Issue,
    _should_stop,
    _update_convergence,
)
from src.config import DocumentConfig
from src.hitl import HumanDecision, HumanInputRequest


def _make_config(**kwargs) -> DocumentConfig:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(kwargs)
    return DocumentConfig(**defaults)


# ── Issue ──────────────────────────────────────────────────────────────────

def test_issue_defaults():
    i = Issue(
        id="I-01",
        description="desc",
        raised_by="challenger",
        cycle=1,
        section_ref="§3",
        status="open",
    )
    assert i.defer_reason is None
    assert i.verified_cycle is None
    assert i.patch_applied is False


# ── CycleState ─────────────────────────────────────────────────────────────

def test_cycle_state_defaults():
    s = CycleState()
    assert s.prd == ""
    assert s.cycle == 0
    assert s.consecutive_clean_cycles == 0
    assert s.prd_path == Path("PRD.md")


def test_cycle_state_prd_path_from_config():
    s = CycleState(prd_path=Path("SPEC.md"))
    assert s.prd_path == Path("SPEC.md")


# ── Convergence logic ──────────────────────────────────────────────────────

def test_should_stop_false_when_no_clean_cycles():
    cfg = _make_config(convergence_cycles=1)
    s = CycleState(consecutive_clean_cycles=0, cycle=1)
    assert _should_stop(s, cfg) is False


def test_should_stop_true_when_clean_cycles_reached():
    cfg = _make_config(convergence_cycles=1)
    s = CycleState(consecutive_clean_cycles=1, cycle=2)
    assert _should_stop(s, cfg) is True


def test_should_stop_true_when_max_cycles_reached():
    cfg = _make_config(max_cycles=3, convergence_cycles=99)
    s = CycleState(cycle=3)
    assert _should_stop(s, cfg) is True


def test_should_stop_false_when_below_max_cycles():
    cfg = _make_config(max_cycles=5, convergence_cycles=99)
    s = CycleState(cycle=2)
    assert _should_stop(s, cfg) is False


def test_update_convergence_increments_when_clean():
    s = CycleState(consecutive_clean_cycles=0)
    _update_convergence(s, valid_count=0, human_required_count=0)
    assert s.consecutive_clean_cycles == 1


def test_update_convergence_resets_when_valid():
    s = CycleState(consecutive_clean_cycles=3)
    _update_convergence(s, valid_count=2, human_required_count=0)
    assert s.consecutive_clean_cycles == 0


def test_update_convergence_resets_when_human_required():
    s = CycleState(consecutive_clean_cycles=2)
    _update_convergence(s, valid_count=0, human_required_count=1)
    assert s.consecutive_clean_cycles == 0


def test_update_convergence_stale_does_not_reset():
    # Stale-only cycles are clean (no valid, no human_required)
    s = CycleState(consecutive_clean_cycles=1)
    _update_convergence(s, valid_count=0, human_required_count=0)
    assert s.consecutive_clean_cycles == 2


# ── CycleContext ───────────────────────────────────────────────────────────

def test_cycle_context_is_base_context_subclass():
    from src.run_state import BaseContext
    assert issubclass(CycleContext, BaseContext)


def test_cycle_context_construction():
    noop = lambda *a, **kw: None
    ctx = CycleContext(
        call_with=noop,
        invoke_for_strategy=noop,
        track_usage=noop,
        track_cost=noop,
        config=_make_config(),
        human_decisions=[],
        read_prd_section=lambda s: "",
        update_issue_registry=noop,
    )
    assert ctx.human_decisions == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_document_loop.py -v 2>&1 | head -20
```
Expected: `ImportError` — `src/document_loop.py` does not exist.

- [ ] **Step 3: Implement data structures in src/document_loop.py**

```python
# src/document_loop.py
"""Document convergence loop — state types, context, and cycle execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .backends import AgentResponse
from .config import DocumentConfig
from .hitl import HumanDecision, HumanInputRequest
from .run_state import BaseContext


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """A critique raised by the Challenger or a persona, tracked across cycles."""

    id: str
    description: str
    raised_by: str          # "challenger" | persona name
    cycle: int
    section_ref: str
    status: str             # "open" | "valid" | "stale" | "deferred" | "resolved"
    defer_reason: str | None = None
    verified_cycle: int | None = None
    patch_applied: bool = False


@dataclass
class CycleState:
    """Mutable state for the document convergence loop."""

    prd: str = ""
    prd_path: Path = field(default_factory=lambda: Path("PRD.md"))
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


@dataclass
class CycleContext(BaseContext):
    """Callback bundle for the document loop.

    Extends ``BaseContext`` (call_with, invoke_for_strategy, track_usage,
    track_cost) with document-specific state.
    """

    config: DocumentConfig
    human_decisions: list[HumanDecision]
    read_prd_section: Callable[[str], str]
    update_issue_registry: Callable[[list[Any]], None]


# ---------------------------------------------------------------------------
# Convergence helpers
# ---------------------------------------------------------------------------

def _should_stop(state: CycleState, config: DocumentConfig) -> bool:
    """Return True when the run should terminate."""
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles


def _update_convergence(
    state: CycleState,
    valid_count: int,
    human_required_count: int,
) -> None:
    """Increment or reset the clean-cycle counter.

    A cycle is clean only when there are zero VALID critiques AND zero
    human_required deferrals.  STALE and out_of_scope/needs_research
    deferrals do not reset the counter.
    """
    if valid_count == 0 and human_required_count == 0:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_document_loop.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/document_loop.py tests/test_document_loop.py
git commit -m "feat(document_loop): add Issue, CycleState, CycleContext, convergence helpers"
```

---

## Task 5: ConvergeStrategy

**Files:**
- Create: `src/document_strategy.py`
- Create: `tests/test_document_strategy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_document_strategy.py
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
import pytest
from src.document_strategy import (
    ConvergeStrategy,
    Patch,
    RawCritique,
    VerifiedCritique,
)
from src.config import DocumentConfig, BackendsConfig
from src.backends.types import AgentResponse
from src.hitl import DeferReason, HumanDecision


def _make_backend(text: str = "{}") -> MagicMock:
    b = MagicMock()
    b.run.return_value = AgentResponse(text=text, cost_usd=0.01, is_error=False,
                                       input_tokens=10, output_tokens=20)
    return b


def _make_config(**kwargs) -> DocumentConfig:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(kwargs)
    return DocumentConfig(**defaults)


def _make_strategy(backends_dict=None, **cfg_kwargs) -> ConvergeStrategy:
    cfg = _make_config(**cfg_kwargs)
    if backends_dict is None:
        backends_dict = {"claude": _make_backend()}
    return ConvergeStrategy(cfg, backends_dict)


# ── Backend role resolution ────────────────────────────────────────────────

def test_builder_uses_research_0():
    codex = _make_backend()
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("codex", "claude")),
    )
    s = ConvergeStrategy(cfg, {"codex": codex, "claude": claude})
    assert s._builder is codex
    assert s._builder_name == "codex"


def test_challenger_uses_research_1():
    codex = _make_backend()
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("codex", "claude")),
    )
    s = ConvergeStrategy(cfg, {"codex": codex, "claude": claude})
    assert s._challenger is claude
    assert s._challenger_name == "claude"


def test_challenger_falls_back_to_primary_when_only_one_research():
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("claude",)),
    )
    s = ConvergeStrategy(cfg, {"claude": claude})
    assert s._challenger is claude


def test_verifier_uses_utility():
    claude = _make_backend()
    utility = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", utility="utility_backend"),
    )
    s = ConvergeStrategy(cfg, {"claude": claude, "utility_backend": utility})
    assert s._verifier is utility


def test_arbitrator_uses_judge():
    claude = _make_backend()
    gemini = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", judge="gemini"),
    )
    s = ConvergeStrategy(cfg, {"claude": claude, "gemini": gemini})
    assert s._arbitrator is gemini


# ── run_builder ────────────────────────────────────────────────────────────

def test_run_builder_returns_text(tmp_path):
    backend = _make_backend("Generated PRD content")
    s = _make_strategy({"claude": backend})

    def call_with(prompt, backend_obj, backend_name):
        return backend_obj.run(prompt, None)

    result = s.run_builder("", [], call_with, human_decisions=[])
    assert result == "Generated PRD content"


def test_run_builder_includes_human_decisions_in_prompt(tmp_path):
    backend = _make_backend("Updated PRD")
    s = _make_strategy({"claude": backend})
    prompts_seen = []

    def call_with(prompt, backend_obj, backend_name):
        prompts_seen.append(prompt)
        return backend_obj.run(prompt, None)

    decision = HumanDecision(
        issue_id="I-01", question="Q?", answer="A!",
        answered_at="2026-01-01T00:00:00+00:00", answered_by="human",
    )
    s.run_builder("existing prd", [], call_with, human_decisions=[decision])
    assert "I-01" in prompts_seen[0]
    assert "A!" in prompts_seen[0]


# ── run_challenger ─────────────────────────────────────────────────────────

def test_run_challenger_parses_json_array():
    response_json = json.dumps([
        {"description": "§3 contradicts §7", "section_ref": "§3", "raised_by": "challenger"}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude": backend})

    def call_with(prompt, b, name):
        return b.run(prompt, None)

    critiques = s.run_challenger("prd text", call_with)
    assert len(critiques) == 1
    assert isinstance(critiques[0], RawCritique)
    assert critiques[0].section_ref == "§3"
    assert critiques[0].raised_by == "challenger"


def test_run_challenger_handles_empty_array():
    backend = _make_backend("[]")
    s = _make_strategy({"claude": backend})
    critiques = s.run_challenger("prd", lambda p, b, n: b.run(p, None))
    assert critiques == []


# ── run_verifier ────────────────────────────────────────────────────────────

def test_run_verifier_classifies_valid():
    raw = [RawCritique(description="d", section_ref="§1", raised_by="challenger")]
    response_json = json.dumps([
        {"description": "d", "section_ref": "§1", "raised_by": "challenger",
         "status": "valid", "defer_reason": None, "question": None, "suggested_answer": None}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude": backend})

    verified = s.run_verifier("prd", raw, lambda p, b, n: b.run(p, None))
    assert len(verified) == 1
    assert verified[0].status == "valid"
    assert verified[0].defer_reason is None


def test_run_verifier_classifies_human_required_with_request():
    raw = [RawCritique(description="ambiguous", section_ref="§5", raised_by="architect")]
    response_json = json.dumps([
        {
            "description": "ambiguous", "section_ref": "§5", "raised_by": "architect",
            "status": "deferred", "defer_reason": "human_required",
            "question": "Which topology?", "suggested_answer": "One per tenant",
        }
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude": backend})

    verified = s.run_verifier("prd", raw, lambda p, b, n: b.run(p, None))
    assert verified[0].defer_reason == DeferReason.HUMAN_REQUIRED
    assert verified[0].question == "Which topology?"
    assert verified[0].suggested_answer == "One per tenant"


# ── run_arbitrator ──────────────────────────────────────────────────────────

def test_run_arbitrator_returns_patches():
    critiques = [
        VerifiedCritique(description="d", section_ref="§3", raised_by="challenger",
                         status="valid")
    ]
    response_json = json.dumps([
        {"section_ref": "§3", "proposed_text": "New text", "rationale": "Because X"}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude": backend})

    patches = s.run_arbitrator("prd", critiques, lambda p, b, n: b.run(p, None))
    assert len(patches) == 1
    assert isinstance(patches[0], Patch)
    assert patches[0].proposed_text == "New text"


def test_run_arbitrator_returns_empty_for_no_valid():
    s = _make_strategy()
    patches = s.run_arbitrator("prd", [], lambda p, b, n: b.run(p, None))
    assert patches == []


# ── run_personas ────────────────────────────────────────────────────────────

def test_run_personas_parallel_returns_merged(monkeypatch):
    backend = _make_backend(json.dumps([
        {"description": "persona critique", "section_ref": "§2", "raised_by": "architect"}
    ]))
    cfg = DocumentConfig(topic="T", goal="G", persona_mode="parallel")
    s = ConvergeStrategy(cfg, {"claude": backend})
    critiques = s.run_personas("prd", lambda p, b, n: b.run(p, None))
    # 3 default personas × 1 critique each = 3 total
    assert len(critiques) == 3
    assert all(isinstance(c, RawCritique) for c in critiques)


def test_run_personas_serial_returns_merged():
    backend = _make_backend(json.dumps([
        {"description": "critique", "section_ref": "§1", "raised_by": "scrum_master"}
    ]))
    cfg = DocumentConfig(topic="T", goal="G", persona_mode="serial")
    s = ConvergeStrategy(cfg, {"claude": backend})
    critiques = s.run_personas("prd", lambda p, b, n: b.run(p, None))
    assert len(critiques) == 3
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_document_strategy.py -v 2>&1 | head -20
```
Expected: `ImportError` — `src/document_strategy.py` does not exist.

- [ ] **Step 3: Implement src/document_strategy.py**

```python
# src/document_strategy.py
"""ConvergeStrategy — standalone multi-LLM document convergence strategy.

NOT a Strategy subclass and NOT registered in _STRATEGY_REGISTRY.
Used exclusively by DocumentRefiner.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from .backends import AgentResponse, Backend, CallOptions
from .config import DocumentConfig
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .prompts import render

# Type alias: (prompt, backend_obj, backend_name) -> AgentResponse
InvokeFn = Callable[[str, Backend, str], AgentResponse]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RawCritique:
    """A critique from the Challenger or a persona (not yet verified)."""
    description: str
    section_ref: str
    raised_by: str


@dataclass
class VerifiedCritique:
    """A critique classified by the Verifier."""
    description: str
    section_ref: str
    raised_by: str
    status: str             # "valid" | "stale" | "deferred"
    defer_reason: str | None = None
    question: str | None = None
    suggested_answer: str | None = None


@dataclass
class Patch:
    """A patch proposal from the Arbitrator."""
    section_ref: str
    proposed_text: str
    rationale: str


# ---------------------------------------------------------------------------
# ConvergeStrategy
# ---------------------------------------------------------------------------

class ConvergeStrategy:
    """Orchestrates the 5-step document convergence cycle.

    Standalone — does NOT extend Strategy and is NOT in _STRATEGY_REGISTRY.
    """

    def __init__(self, config: DocumentConfig, backends: dict[str, Backend]) -> None:
        self._config = config
        research = config.backends.research
        primary = config.backends.primary

        builder_name = research[0] if research else primary
        challenger_name = research[1] if len(research) > 1 else primary
        verifier_name = config.backends.utility_or_primary
        arbitrator_name = config.backends.judge_or_primary

        def _get(name: str) -> tuple[Backend, str]:
            backend = backends.get(name) or backends[primary]
            return backend, name

        self._builder, self._builder_name = _get(builder_name)
        self._challenger, self._challenger_name = _get(challenger_name)
        self._verifier, self._verifier_name = _get(verifier_name)
        self._arbitrator, self._arbitrator_name = _get(arbitrator_name)
        self._persona_backend, self._persona_name = backends[primary], primary

    # ── Builder ─────────────────────────────────────────────────────────────

    def run_builder(
        self,
        prd: str,
        patches: list[Patch],
        invoke: InvokeFn,
        *,
        human_decisions: list[HumanDecision],
    ) -> str:
        """Generate the initial PRD (cycle 1) or apply validated patches (cycle N+)."""
        human_block = _format_human_decisions(human_decisions)
        patches_block = _format_patches(patches)
        prompt = render(
            "prd_builder.md",
            topic=self._config.topic,
            goal=self._config.goal,
            source_material=self._config.source_material,
            current_prd=prd,
            patches=patches_block,
            human_decisions=human_block,
        )
        resp = invoke(prompt, self._builder, self._builder_name)
        return resp.text

    # ── Challenger ──────────────────────────────────────────────────────────

    def run_challenger(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run internal consistency critique. Returns list of raw critiques."""
        prompt = render("prd_challenger.md", prd=prd, topic=self._config.topic)
        resp = invoke(prompt, self._challenger, self._challenger_name)
        return _parse_raw_critiques(resp.text, default_raised_by="challenger")

    # ── Personas ────────────────────────────────────────────────────────────

    def run_personas(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run all personas. Parallel or serial per config.persona_mode."""
        if self._config.persona_mode == "parallel":
            return self._run_personas_parallel(prd, invoke)
        return self._run_personas_serial(prd, invoke)

    def _run_personas_parallel(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        with ThreadPoolExecutor(max_workers=len(self._config.personas)) as pool:
            futures = {
                pool.submit(self._invoke_persona, persona, prd, invoke): persona
                for persona in self._config.personas
            }
            for future in as_completed(futures):
                results.extend(future.result())
        return results

    def _run_personas_serial(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        for persona in self._config.personas:
            results.extend(self._invoke_persona(persona, prd, invoke))
        return results

    def _invoke_persona(self, persona: Any, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        prompt_file = persona.prompt_file or f"prd_persona_{persona.name}.md"
        prompt = render(prompt_file, prd=prd, topic=self._config.topic)
        resp = invoke(prompt, self._persona_backend, self._persona_name)
        return _parse_raw_critiques(resp.text, default_raised_by=persona.name)

    # ── Verifier ────────────────────────────────────────────────────────────

    def run_verifier(
        self, prd: str, critiques: list[RawCritique], invoke: InvokeFn
    ) -> list[VerifiedCritique]:
        """Classify each critique as valid / stale / deferred."""
        if not critiques:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref, "raised_by": c.raised_by}
             for c in critiques],
            indent=2,
        )
        prompt = render("prd_verify.md", prd=prd, critiques_json=critiques_json)
        resp = invoke(prompt, self._verifier, self._verifier_name)
        return _parse_verified_critiques(resp.text)

    # ── Arbitrator ──────────────────────────────────────────────────────────

    def run_arbitrator(
        self, prd: str, critiques: list[VerifiedCritique], invoke: InvokeFn
    ) -> list[Patch]:
        """Generate patch proposals for all VALID critiques."""
        valid = [c for c in critiques if c.status == "valid"]
        if not valid:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref}
             for c in valid],
            indent=2,
        )
        prompt = render("prd_arbitrate.md", prd=prd, valid_critiques_json=critiques_json)
        resp = invoke(prompt, self._arbitrator, self._arbitrator_name)
        return _parse_patches(resp.text)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Any:
    """Extract JSON from model output (tolerates markdown fences)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    bracket = text.find("[")
    if bracket != -1:
        return json.loads(text[bracket:])
    return json.loads(text)


def _parse_raw_critiques(text: str, *, default_raised_by: str) -> list[RawCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        RawCritique(
            description=item.get("description", ""),
            section_ref=item.get("section_ref", ""),
            raised_by=item.get("raised_by", default_raised_by),
        )
        for item in items
        if isinstance(item, dict) and item.get("description")
    ]


def _parse_verified_critiques(text: str) -> list[VerifiedCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        VerifiedCritique(
            description=item.get("description", ""),
            section_ref=item.get("section_ref", ""),
            raised_by=item.get("raised_by", ""),
            status=item.get("status", "stale"),
            defer_reason=item.get("defer_reason"),
            question=item.get("question"),
            suggested_answer=item.get("suggested_answer"),
        )
        for item in items
        if isinstance(item, dict)
    ]


def _parse_patches(text: str) -> list[Patch]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        Patch(
            section_ref=item.get("section_ref", ""),
            proposed_text=item.get("proposed_text", ""),
            rationale=item.get("rationale", ""),
        )
        for item in items
        if isinstance(item, dict) and item.get("proposed_text")
    ]


def _format_human_decisions(decisions: list[HumanDecision]) -> str:
    if not decisions:
        return ""
    lines = ["--- HUMAN DECISIONS (ground truth — do not contradict) ---\n"]
    for d in decisions:
        lines.append(f"[{d.issue_id}] {d.question}\n  Answer: {d.answer}\n")
    lines.append("---")
    return "\n".join(lines)


def _format_patches(patches: list[Patch]) -> str:
    if not patches:
        return "(no patches — generate initial document)"
    lines = []
    for i, p in enumerate(patches, 1):
        lines.append(f"Patch {i} [{p.section_ref}]: {p.proposed_text}\nRationale: {p.rationale}")
    return "\n\n".join(lines)
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_document_strategy.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/document_strategy.py tests/test_document_strategy.py
git commit -m "feat(document_strategy): add ConvergeStrategy, RawCritique, VerifiedCritique, Patch"
```

---

## Task 6: run_cycle function

Add `run_cycle()` to `src/document_loop.py` and test the full cycle flow.

**Files:**
- Modify: `src/document_loop.py` (append `run_cycle` and helpers)
- Modify: `tests/test_document_loop.py` (append cycle tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_document_loop.py`:

```python
# --- run_cycle tests --------------------------------------------------------
from unittest.mock import MagicMock, patch
from src.document_loop import run_cycle
from src.document_strategy import ConvergeStrategy, RawCritique, VerifiedCritique, Patch
from src.hitl import DeferReason


def _make_strategy_mock(
    builder_text="PRD v2",
    challenger_critiques=None,
    persona_critiques=None,
    verified=None,
    patches=None,
) -> MagicMock:
    s = MagicMock(spec=ConvergeStrategy)
    s.run_builder.return_value = builder_text
    s.run_challenger.return_value = challenger_critiques or []
    s.run_personas.return_value = persona_critiques or []
    s.run_verifier.return_value = verified or []
    s.run_arbitrator.return_value = patches or []
    return s


def _make_ctx(config=None) -> CycleContext:
    noop = lambda *a, **kw: None
    return CycleContext(
        call_with=noop,
        invoke_for_strategy=noop,
        track_usage=noop,
        track_cost=noop,
        config=config or _make_config(),
        human_decisions=[],
        read_prd_section=lambda s: "",
        update_issue_registry=noop,
    )


def test_run_cycle_increments_cycle():
    state = CycleState()
    strategy = _make_strategy_mock()
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert state.cycle == 1


def test_run_cycle_updates_prd():
    state = CycleState(prd="old prd")
    strategy = _make_strategy_mock(builder_text="new prd")
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert state.prd == "new prd"


def test_run_cycle_appends_prd_version():
    state = CycleState(prd="old")
    strategy = _make_strategy_mock(builder_text="new")
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert "new" in state.prd_versions


def test_run_cycle_clean_increments_consecutive():
    state = CycleState()
    strategy = _make_strategy_mock(verified=[])
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert state.consecutive_clean_cycles == 1


def test_run_cycle_valid_critiques_reset_consecutive():
    state = CycleState(consecutive_clean_cycles=2)
    verified = [VerifiedCritique(description="d", section_ref="§1",
                                 raised_by="challenger", status="valid")]
    strategy = _make_strategy_mock(verified=verified)
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert state.consecutive_clean_cycles == 0


def test_run_cycle_human_required_noninteractive_returns_pending():
    state = CycleState()
    verified = [VerifiedCritique(
        description="d", section_ref="§5", raised_by="architect",
        status="deferred", defer_reason=DeferReason.HUMAN_REQUIRED,
        question="Q?", suggested_answer="A",
    )]
    strategy = _make_strategy_mock(verified=verified)
    valid_count, _, _ = run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert len(state.pending_human_inputs) == 1
    assert state.consecutive_clean_cycles == 0


def test_run_cycle_returns_counts():
    valid = [VerifiedCritique(description="d", section_ref="§1",
                              raised_by="challenger", status="valid")]
    stale = [VerifiedCritique(description="s", section_ref="§2",
                              raised_by="challenger", status="stale")]
    strategy = _make_strategy_mock(verified=valid + stale)
    state = CycleState()
    v_count, s_count, d_count = run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert v_count == 1
    assert s_count == 1
    assert d_count == 0


def test_run_cycle_adds_issues_to_registry():
    verified = [VerifiedCritique(description="d", section_ref="§1",
                                 raised_by="challenger", status="valid")]
    strategy = _make_strategy_mock(verified=verified)
    state = CycleState()
    run_cycle(state, _make_ctx(), strategy, interactive=False)
    assert len(state.issue_registry) == 1
    assert state.issue_registry[0].status == "valid"
    assert state.issue_registry[0].id == "I-01"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_document_loop.py -v -k "run_cycle" 2>&1 | head -20
```
Expected: `ImportError` — `run_cycle` not defined.

- [ ] **Step 3: Implement run_cycle in document_loop.py**

Append to `src/document_loop.py`:

```python
# ---------------------------------------------------------------------------
# Cycle execution
# ---------------------------------------------------------------------------

def run_cycle(
    state: CycleState,
    ctx: CycleContext,
    strategy: Any,
    *,
    interactive: bool = True,
) -> tuple[int, int, int]:
    """Execute one convergence cycle.

    Returns:
        Tuple of (valid_count, stale_count, deferred_count).
    """
    state.cycle += 1

    # 1. Builder — generate or patch
    patches = [
        p for p in getattr(state, "_pending_patches", [])
    ]
    prd = strategy.run_builder(
        state.prd, patches, ctx.call_with, human_decisions=ctx.human_decisions
    )
    state.prd = prd
    state.prd_versions.append(prd)

    # 2. Challenger
    raw_critiques = strategy.run_challenger(prd, ctx.call_with)

    # 3. Personas
    persona_critiques = strategy.run_personas(prd, ctx.call_with)

    all_raw = raw_critiques + persona_critiques

    # 4. Verifier
    verified = strategy.run_verifier(prd, all_raw, ctx.call_with)

    # 5. Classify
    valid = [v for v in verified if v.status == "valid"]
    stale = [v for v in verified if v.status == "stale"]
    deferred = [v for v in verified if v.status == "deferred"]
    human_required = [
        v for v in deferred if v.defer_reason == DeferReason.HUMAN_REQUIRED
    ]

    # 6. HITL gate
    if human_required:
        requests = _make_human_requests(human_required, state.cycle)
        state.pending_human_inputs = requests
        if interactive:
            from .hitl import collect_interactive
            decisions = collect_interactive(requests)
            state.human_decisions.extend(decisions)
            ctx.human_decisions.extend(decisions)
            state.pending_human_inputs = []
        # In non-interactive mode: pending remains; caller exits

    # 7. Arbitrator — patches for VALID only
    new_patches = strategy.run_arbitrator(prd, valid, ctx.call_with)
    state.__dict__.setdefault("_pending_patches", [])
    state._pending_patches = new_patches

    # 8. Update issue registry
    _register_issues(state, verified)

    # 9. Update convergence counter
    _update_convergence(
        state,
        valid_count=len(valid),
        human_required_count=len(human_required),
    )

    return len(valid), len(stale), len(deferred)


def _make_human_requests(
    human_required: list[Any], cycle: int
) -> list[HumanInputRequest]:
    """Build HumanInputRequest objects from human_required VerifiedCritiques."""
    requests = []
    for v in human_required:
        requests.append(HumanInputRequest(
            issue_id="",  # assigned when added to registry
            question=v.question or v.description,
            context=v.section_ref,
            suggested_answer=v.suggested_answer or "",
            cycle=cycle,
        ))
    return requests


def _register_issues(state: CycleState, verified: list[Any]) -> None:
    """Add newly verified critiques to the issue registry with sequential IDs."""
    next_id = len(state.issue_registry) + 1
    for i, v in enumerate(verified):
        issue = Issue(
            id=f"I-{next_id + i:02d}",
            description=v.description,
            raised_by=v.raised_by,
            cycle=state.cycle,
            section_ref=v.section_ref,
            status=v.status,
            defer_reason=v.defer_reason,
            verified_cycle=state.cycle,
        )
        state.issue_registry.append(issue)
```

Also add the `DeferReason` import at the top of `document_loop.py` (it's already imported from `hitl`). No change needed.

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_document_loop.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/document_loop.py tests/test_document_loop.py
git commit -m "feat(document_loop): add run_cycle, issue registry, HITL gate"
```

---

## Task 7: DocumentRefiner

**Files:**
- Create: `src/document_refiner.py`
- Create: `tests/test_document_refiner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_document_refiner.py
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from src.config import DocumentConfig, ArtifactConfig, BackendsConfig
from src.document_refiner import DocumentRefiner
from src.backends.types import AgentResponse


def _make_backend(text: str = "Generated content") -> MagicMock:
    b = MagicMock()
    b.run.return_value = AgentResponse(text=text, cost_usd=0.0, is_error=False,
                                       input_tokens=5, output_tokens=10)
    b.check_available.return_value = True
    return b


def _make_refiner(tmp_path: Path, **cfg_kwargs) -> DocumentRefiner:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(cfg_kwargs)
    cfg = DocumentConfig(**defaults)
    backend = _make_backend()
    return DocumentRefiner(
        config=cfg,
        output_dir=tmp_path / "output",
        backends={"claude": backend},
    )


def test_refiner_creates_output_dir(tmp_path):
    r = _make_refiner(tmp_path)
    r._setup_dirs()
    assert (tmp_path / "output").exists()
    assert (tmp_path / "output" / ".run").exists()


def test_refiner_writes_primary_artifact(tmp_path):
    r = _make_refiner(tmp_path)
    r._setup_dirs()
    r._write_primary_artifact("PRD content here")
    artifact = tmp_path / "output" / "PRD.md"
    assert artifact.exists()
    assert artifact.read_text() == "PRD content here"


def test_refiner_phase3_writes_readme_and_index(tmp_path):
    backend = _make_backend("Generated index content")
    cfg = DocumentConfig(topic="T", goal="G")
    r = DocumentRefiner(
        config=cfg,
        output_dir=tmp_path / "out",
        backends={"claude": backend},
    )
    r._setup_dirs()
    r._write_primary_artifact("PRD content")
    with patch.object(r, "_invoke", return_value=AgentResponse(
        text="# README\ncontent", cost_usd=0.0, is_error=False,
        input_tokens=5, output_tokens=10
    )):
        r._run_phase3()
    assert (tmp_path / "out" / "README.md").exists()
    assert (tmp_path / "out" / "DOCS_INDEX.md").exists()


def test_refiner_writes_run_manifest(tmp_path):
    r = _make_refiner(tmp_path)
    r._setup_dirs()
    r._write_primary_artifact("content")
    r._write_run_manifest(cycles=3, total_cost=0.05)
    manifest = tmp_path / "output" / ".run" / "run_manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text())
    assert data["cycles"] == 3
    assert data["topic"] == "T"


def test_refiner_writes_issue_registry(tmp_path):
    from src.document_loop import CycleState, Issue
    r = _make_refiner(tmp_path)
    r._setup_dirs()
    state = CycleState()
    state.issue_registry.append(Issue(
        id="I-01", description="d", raised_by="challenger",
        cycle=1, section_ref="§1", status="valid",
    ))
    r._write_issue_registry(state)
    reg = tmp_path / "output" / ".run" / "issue_registry.json"
    assert reg.exists()
    data = json.loads(reg.read_text())
    assert data[0]["id"] == "I-01"


def test_refiner_no_interactive_exits_nonzero_on_human_required(tmp_path, monkeypatch):
    from src.document_loop import CycleState
    from src.document_strategy import VerifiedCritique
    from src.hitl import DeferReason

    backend = _make_backend("PRD text")
    cfg = DocumentConfig(topic="T", goal="G", max_cycles=1)
    r = DocumentRefiner(config=cfg, output_dir=tmp_path / "out",
                        backends={"claude": backend})

    verified = [VerifiedCritique(
        description="d", section_ref="§1", raised_by="architect",
        status="deferred", defer_reason=DeferReason.HUMAN_REQUIRED,
        question="Q?", suggested_answer="A",
    )]

    with patch("src.document_refiner.ConvergeStrategy") as MockStrategy:
        mock_s = MagicMock()
        mock_s.run_builder.return_value = "PRD"
        mock_s.run_challenger.return_value = []
        mock_s.run_personas.return_value = []
        mock_s.run_verifier.return_value = verified
        mock_s.run_arbitrator.return_value = []
        MockStrategy.return_value = mock_s

        exit_code = r.run(interactive=False)

    assert exit_code != 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_document_refiner.py -v 2>&1 | head -20
```
Expected: `ImportError`.

- [ ] **Step 3: Implement src/document_refiner.py**

```python
# src/document_refiner.py
"""DocumentRefiner — document convergence orchestrator.

Sibling to AutoResearcher. Runs Phase 1 (PRD convergence),
Phase 2 (artifact expansion), and Phase 3 (index generation).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import AgentResponse, Backend, CallOptions
from .config import ArtifactConfig, DocumentConfig
from .document_loop import CycleContext, CycleState, Issue, _should_stop, run_cycle
from .document_strategy import ConvergeStrategy, Patch
from .hitl import (
    DeferReason,
    HumanDecision,
    append_human_decisions,
    load_human_decisions,
    write_pending_questions,
)
from .prompts import render

log = logging.getLogger("autoresearch")

_EXIT_HUMAN_REQUIRED = 2


class DocumentRefiner:
    """Orchestrates a document convergence run (refine subcommand).

    Phase 1 — Convergence: PRD refined through adversarial cycles until clean.
    Phase 2 — Expansion: Execution and companion artifacts generated from
               the converged PRD.
    Phase 3 — Indexing: DOCS_INDEX.md and README.md auto-generated.
    """

    def __init__(
        self,
        config: DocumentConfig,
        output_dir: Path,
        backends: dict[str, Backend],
        resume: bool = False,
    ) -> None:
        self._config = config
        self._output_dir = output_dir
        self._run_dir = output_dir / ".run"
        self._backends = backends
        self._resume = resume
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

    # ── Public entry point ──────────────────────────────────────────────────

    def run(self, *, interactive: bool = True) -> int:
        """Run all three phases. Returns exit code (0 on success, 2 on HITL pause)."""
        self._setup_dirs()

        strategy = ConvergeStrategy(self._config, self._backends)
        state = self._init_state()

        ctx = CycleContext(
            call_with=self._invoke,
            invoke_for_strategy=self._invoke,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            config=self._config,
            human_decisions=state.human_decisions,
            read_prd_section=lambda ref: "",
            update_issue_registry=lambda issues: None,
        )

        # Phase 1 — Convergence
        while not _should_stop(state, self._config):
            valid_count, stale_count, deferred_count = run_cycle(
                state, ctx, strategy, interactive=interactive
            )
            log.info(
                "[cycle %d] valid=%d stale=%d deferred=%d clean_streak=%d",
                state.cycle, valid_count, stale_count, deferred_count,
                state.consecutive_clean_cycles,
            )
            self._write_cycle_snapshot(state)
            self._write_issue_registry(state)

            if state.pending_human_inputs and not interactive:
                self._handle_hitl_pause(state)
                return _EXIT_HUMAN_REQUIRED

        # Write converged primary artifact
        self._write_primary_artifact(state.prd)
        log.info("[refine] Phase 1 complete — %s converged in %d cycle(s).",
                 self._config.primary_artifact, state.cycle)

        # Phase 2 — Expansion
        self._run_phase2(state.prd, strategy, ctx)

        # Phase 3 — Indexing
        self._run_phase3()

        # Finalize
        self._write_run_manifest(cycles=state.cycle, total_cost=self._total_cost)
        log.info("[refine] Done. Output at: %s", self._output_dir)
        return 0

    # ── Phase 2: Expansion ──────────────────────────────────────────────────

    def _run_phase2(self, prd: str, strategy: ConvergeStrategy, ctx: CycleContext) -> None:
        for artifact in self._config.artifacts:
            log.info("[phase2] Generating %s ...", artifact.name)
            content = self._generate_artifact(prd, artifact, strategy, ctx)
            out_path = self._output_dir / artifact.name
            out_path.write_text(content, encoding="utf-8")
            log.info("[phase2] Wrote %s", artifact.name)

    def _generate_artifact(
        self,
        prd: str,
        artifact: ArtifactConfig,
        strategy: ConvergeStrategy,
        ctx: CycleContext,
    ) -> str:
        stem = Path(artifact.name).stem
        prompt_file = artifact.prompt_file or f"artifact_{stem}.md"
        try:
            prompt = render(prompt_file, prd=prd, topic=self._config.topic,
                            goal=self._config.goal)
        except FileNotFoundError:
            log.warning("Prompt file not found for %s — skipping.", artifact.name)
            return f"# {artifact.name}\n\n(prompt not configured)\n"

        builder_name = (
            self._config.backends.research[0]
            if self._config.backends.research
            else self._config.backends.primary
        )
        backend = self._backends.get(builder_name) or self._backends[self._config.backends.primary]
        resp = self._invoke(prompt, backend, builder_name)

        if artifact.review:
            content = resp.text
            raw = strategy.run_challenger(content, ctx.call_with)
            verified = strategy.run_verifier(content, raw, ctx.call_with)
            valid = [v for v in verified if v.status == "valid"]
            if valid:
                patches = strategy.run_arbitrator(content, valid, ctx.call_with)
                content = strategy.run_builder(content, patches, ctx.call_with,
                                               human_decisions=ctx.human_decisions)
            return content

        return resp.text

    # ── Phase 3: Indexing ───────────────────────────────────────────────────

    def _run_phase3(self) -> None:
        manifest = self._build_artifact_manifest()
        builder_name = (
            self._config.backends.research[0]
            if self._config.backends.research
            else self._config.backends.primary
        )
        backend = self._backends.get(builder_name) or self._backends[self._config.backends.primary]

        readme_prompt = render(
            "generate_readme.md",
            topic=self._config.topic,
            goal=self._config.goal,
            primary_artifact=self._config.primary_artifact,
            artifact_manifest=manifest,
        )
        readme_resp = self._invoke(readme_prompt, backend, builder_name)
        (self._output_dir / "README.md").write_text(readme_resp.text, encoding="utf-8")

        index_prompt = render(
            "generate_docs_index.md",
            topic=self._config.topic,
            goal=self._config.goal,
            primary_artifact=self._config.primary_artifact,
            artifact_manifest=manifest,
            personas=", ".join(p.name for p in self._config.personas),
        )
        index_resp = self._invoke(index_prompt, backend, builder_name)
        (self._output_dir / "DOCS_INDEX.md").write_text(index_resp.text, encoding="utf-8")

    def _build_artifact_manifest(self) -> str:
        lines = [f"- {self._config.primary_artifact} (primary, always present)"]
        for a in self._config.artifacts:
            lines.append(f"- {a.name} (layer:{a.layer}, review:{a.review})")
        lines.append("- DOCS_INDEX.md (auto-generated)")
        lines.append("- README.md (auto-generated)")
        return "\n".join(lines)

    # ── State management ────────────────────────────────────────────────────

    def _init_state(self) -> CycleState:
        state = CycleState(prd_path=Path(self._config.primary_artifact))
        if self._resume:
            decisions_path = self._run_dir / "human_decisions.json"
            state.human_decisions = load_human_decisions(decisions_path)
        return state

    def _setup_dirs(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "cycles").mkdir(exist_ok=True)

    def _write_primary_artifact(self, content: str) -> None:
        path = self._output_dir / self._config.primary_artifact
        path.write_text(content, encoding="utf-8")

    def _write_cycle_snapshot(self, state: CycleState) -> None:
        snap = self._run_dir / "cycles" / f"cycle_{state.cycle:03d}.md"
        snap.write_text(
            f"# Cycle {state.cycle}\n\n"
            f"Valid issues: {sum(1 for i in state.issue_registry if i.status == 'valid')}\n"
            f"Clean streak: {state.consecutive_clean_cycles}\n\n"
            f"## PRD snapshot\n\n{state.prd[:2000]}\n",
            encoding="utf-8",
        )
        version_path = self._run_dir / f"{Path(self._config.primary_artifact).stem}_v{state.cycle}.md"
        version_path.write_text(state.prd, encoding="utf-8")

    def _write_issue_registry(self, state: CycleState) -> None:
        path = self._run_dir / "issue_registry.json"
        path.write_text(
            json.dumps([dataclasses.asdict(i) for i in state.issue_registry], indent=2),
            encoding="utf-8",
        )

    def _write_run_manifest(self, *, cycles: int, total_cost: float) -> None:
        manifest = {
            "topic": self._config.topic,
            "goal": self._config.goal,
            "primary_artifact": self._config.primary_artifact,
            "cycles": cycles,
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": [a.name for a in self._config.artifacts],
        }
        (self._run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def _handle_hitl_pause(self, state: CycleState) -> None:
        pending_path = self._run_dir / "pending_questions.json"
        write_pending_questions(state.pending_human_inputs, pending_path)
        print(
            f"\n[refine] {len(state.pending_human_inputs)} question(s) require human input.\n"
            f"Fill in answers in: {pending_path}\n"
            f"Then re-run with --resume to continue.\n"
        )

    # ── Backend invocation ──────────────────────────────────────────────────

    def _invoke(self, prompt: str, backend: Backend, backend_name: str) -> AgentResponse:
        opts = CallOptions(max_turns=10, timeout_seconds=600)
        resp = backend.run(prompt, opts)
        self._track_usage(resp, backend_name)
        return resp

    def _track_usage(self, resp: AgentResponse, backend_name: str) -> None:
        self._total_cost += resp.cost_usd
        self._total_input_tokens += resp.input_tokens
        self._total_output_tokens += resp.output_tokens

    def _track_cost(self, cost: float, backend_name: str) -> None:
        self._total_cost += cost
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/test_document_refiner.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/document_refiner.py tests/test_document_refiner.py
git commit -m "feat(document_refiner): add DocumentRefiner with Phase 1/2/3 orchestration"
```

---

## Task 8: CLI refine subcommand

**Files:**
- Modify: `src/cli.py`
- Modify: `tests/test_cli.py` (append refine tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
# ── refine subcommand tests ─────────────────────────────────────────────────
import textwrap
from unittest.mock import patch, MagicMock
from src.cli import main


def _write_doc_yaml(tmp_path, content=""):
    p = tmp_path / "doc.yaml"
    p.write_text(textwrap.dedent(content or """
        document:
          topic: "T"
          goal: "G"
    """))
    return p


def test_cli_refine_subcommand_exits_0_on_success(tmp_path):
    cfg = _write_doc_yaml(tmp_path)
    with patch("src.cli.DocumentRefiner") as MockRefiner:
        instance = MagicMock()
        instance.run.return_value = 0
        MockRefiner.return_value = instance
        with patch("src.cli.get_backends", return_value={"claude": MagicMock(check_available=lambda: True)}):
            code = main(["refine", "--config", str(cfg), "--output", str(tmp_path / "out")])
    assert code == 0


def test_cli_refine_missing_document_key_exits_1(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("research:\n  topic: T\n  goal: G\n  dimensions: []\n")
    code = main(["refine", "--config", str(cfg)])
    assert code == 1


def test_cli_refine_no_interactive_flag(tmp_path):
    cfg = _write_doc_yaml(tmp_path)
    kwargs_seen = {}
    with patch("src.cli.DocumentRefiner") as MockRefiner:
        instance = MagicMock()
        instance.run.side_effect = lambda **kw: kwargs_seen.update(kw) or 0
        MockRefiner.return_value = instance
        with patch("src.cli.get_backends", return_value={"claude": MagicMock(check_available=lambda: True)}):
            main(["refine", "--config", str(cfg), "--no-interactive",
                  "--output", str(tmp_path / "out")])
    assert kwargs_seen.get("interactive") is False


def test_cli_refine_resume_flag_passed_to_refiner(tmp_path):
    cfg = _write_doc_yaml(tmp_path)
    init_kwargs = {}
    with patch("src.cli.DocumentRefiner") as MockRefiner:
        def capture(**kw):
            init_kwargs.update(kw)
            m = MagicMock()
            m.run.return_value = 0
            return m
        MockRefiner.side_effect = capture
        with patch("src.cli.get_backends", return_value={"claude": MagicMock(check_available=lambda: True)}):
            main(["refine", "--config", str(cfg), "--resume",
                  "--output", str(tmp_path / "out")])
    assert init_kwargs.get("resume") is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_cli.py -v -k "refine" 2>&1 | head -20
```
Expected: `SystemExit` or `error: argument subcommand: invalid choice`.

- [ ] **Step 3: Rewrite cli.py with subcommands**

Replace `src/cli.py` with the following (the existing `run` logic becomes the `run` subcommand):

```python
# src/cli.py
"""Entry point for the autoresearch-claude framework."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .backends import VALID_BACKENDS, get_backend, get_backends
from .config import VALID_STRATEGIES, DocumentConfig, ResearchConfig
from .document_refiner import DocumentRefiner
from .orchestrator import AutoResearcher
from .strategy import get_strategy


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description="Autonomous research loop powered by AI coding agent CLIs.",
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    subparsers = parser.add_subparsers(dest="subcommand")

    # ── run (existing research mode) ──────────────────────────────────────
    run_parser = subparsers.add_parser("run", help="Run the research loop.")
    run_parser.add_argument("--config", type=Path, required=True)
    run_parser.add_argument("--backend", choices=VALID_BACKENDS, default=None)
    run_parser.add_argument("--output", type=Path, default=None)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--synthesize", action="store_true")
    run_parser.add_argument("--strategy", choices=VALID_STRATEGIES, default=None)

    # ── refine (document mode) ────────────────────────────────────────────
    refine_parser = subparsers.add_parser("refine", help="Run document convergence loop.")
    refine_parser.add_argument("--config", type=Path, required=True)
    refine_parser.add_argument("--output", type=Path, default=None)
    refine_parser.add_argument("--resume", action="store_true")
    refine_parser.add_argument("--no-interactive", action="store_true", dest="no_interactive")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("autoresearch")

    if args.subcommand is None:
        parser.print_help()
        return 1

    if args.subcommand == "refine":
        return _run_refine(args, log)

    return _run_research(args, log)


def _run_refine(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = DocumentConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load document config: %s", exc)
        return 1

    output_dir: Path = args.output or Path("output") / config_path.stem
    output_dir = output_dir.resolve()

    all_names = config.backends.all_backend_names()
    backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error("%s CLI not available.", name)
            return 1

    refiner = DocumentRefiner(
        config=config,
        output_dir=output_dir,
        backends=backends,
        resume=args.resume,
    )

    try:
        return refiner.run(interactive=not args.no_interactive)
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1


def _run_research(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = ResearchConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load config: %s", exc)
        return 1

    backend_name = args.backend or config.execution.backend
    backend = get_backend(backend_name)
    strategy_name = args.strategy or config.execution.strategy
    output_dir: Path = args.output or Path("output") / config_path.stem
    output_dir = output_dir.resolve()

    if not args.resume and not args.synthesize and output_dir.exists():
        iters_dir = output_dir / "iterations"
        if iters_dir.exists() and list(iters_dir.glob("iter_*.md")):
            log.info("Found existing iterations. Use --resume to continue.")

    all_names = config.execution.backends.all_backend_names()
    if strategy_name == "single":
        all_names = {backend_name}
    backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error("%s CLI not found or not responding.", name)
            return 1

    strategy = get_strategy(
        strategy_name, config.execution.backends,
        config.execution.strategy_config, backends,
    )
    researcher = AutoResearcher(
        config=config, backend=backend, output_dir=output_dir,
        backends=backends, strategy=strategy,
        resume=args.resume, config_path=config_path,
    )

    try:
        if args.synthesize:
            researcher.synthesize_only()
        else:
            researcher.run()
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run all tests to confirm no regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: all existing tests PASS; new CLI refine tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cli.py tests/test_cli.py
git commit -m "feat(cli): add refine subcommand with --no-interactive and --resume"
```

---

## Task 9: Prompt files

**Files:**
- Create: `prompts/prd_builder.md`
- Create: `prompts/prd_challenger.md`
- Create: `prompts/prd_verify.md`
- Create: `prompts/prd_arbitrate.md`
- Create: `prompts/prd_persona_architect.md`
- Create: `prompts/prd_persona_scrum_master.md`
- Create: `prompts/prd_persona_product_owner.md`
- Create: `prompts/generate_readme.md`
- Create: `prompts/generate_docs_index.md`

All prompts use Python `str.format()` placeholders (`{variable_name}`).

- [ ] **Step 1: Create prompts/prd_builder.md**

```markdown
You are a senior technical writer and product architect tasked with producing
or refining a Product Requirements Document (PRD).

## Topic
{topic}

## Goal
{goal}

## Source Material
{source_material}

{human_decisions}

## Current Document
{current_prd}

## Patches to Apply
{patches}

---

## Instructions

If the current document is empty and there are no patches, generate the initial
PRD from the source material and topic. The document must be comprehensive,
structured, and execution-ready.

If patches are provided, apply each patch faithfully. Where a HUMAN DECISIONS
block is present, treat every answer as ground truth — do not contradict or
soften them.

Output ONLY the complete, updated PRD in Markdown. No preamble, no explanation.
```

- [ ] **Step 2: Create prompts/prd_challenger.md**

```markdown
You are an internal consistency auditor reviewing a Product Requirements Document.

## Topic
{topic}

## Document to Review
{prd}

---

## Instructions

Identify internal contradictions, missing definitions, scope ambiguities, and
implementation gaps. For each issue you find, provide:

- A precise description of the problem
- The section reference where it appears (e.g. §3.2, §7)
- Your role: "challenger"

Respond with a JSON array only. No preamble or explanation.

Example format:
```json
[
  {{
    "description": "§3 states X but §7 requires Y — these are contradictory.",
    "section_ref": "§3",
    "raised_by": "challenger"
  }}
]
```

If the document has no internal issues, respond with an empty array: `[]`
```

- [ ] **Step 3: Create prompts/prd_verify.md**

```markdown
You are a verification specialist. Your job is to classify each critique below
as VALID, STALE, or DEFERRED — based solely on what the document actually says.

## Document
{prd}

## Critiques to Verify
```json
{critiques_json}
```

---

## Classification Rules

- **valid**: The critique is accurate — the document actually has this problem.
- **stale**: The document already addresses this concern adequately.
- **deferred (out_of_scope)**: The critique is about something outside the document's
  stated scope. Does NOT block convergence.
- **deferred (needs_research)**: Resolving this requires information not in the
  document, but the pipeline can generate it. Does NOT block convergence.
- **deferred (human_required)**: Only a human stakeholder can answer this.
  BLOCKS convergence. You must also provide a focused `question` and a
  `suggested_answer` (your best guess) for the operator.

## Output Format

Return a JSON array with one object per input critique, in the same order.

```json
[
  {{
    "description": "original description",
    "section_ref": "§X",
    "raised_by": "challenger",
    "status": "valid",
    "defer_reason": null,
    "question": null,
    "suggested_answer": null
  }},
  {{
    "description": "ambiguous topology",
    "section_ref": "§5",
    "raised_by": "architect",
    "status": "deferred",
    "defer_reason": "human_required",
    "question": "Does each regulated tenant get a dedicated AWS account?",
    "suggested_answer": "Yes — one account per regulated tenant for maximum isolation."
  }}
]
```

Output ONLY the JSON array. No preamble.
```

- [ ] **Step 4: Create prompts/prd_arbitrate.md**

```markdown
You are an expert technical arbitrator. Your job is to generate precise patch
proposals for each VALID critique listed below.

## Document
{prd}

## Valid Critiques Requiring Patches
```json
{valid_critiques_json}
```

---

## Instructions

For each critique, propose a targeted text replacement that resolves the issue
without altering unrelated sections. Keep patches minimal and focused.

Output ONLY a JSON array. No preamble.

```json
[
  {{
    "section_ref": "§3",
    "proposed_text": "The exact replacement text for this section...",
    "rationale": "One sentence explaining why this patch resolves the critique."
  }}
]
```

If you cannot propose a patch for a critique, omit it from the array.
```

- [ ] **Step 5: Create prompts/prd_persona_architect.md**

```markdown
You are a Cloud Solutions Architect with 15+ years of experience in
distributed systems, Kubernetes, and multi-cloud deployments.

## Document Under Review
{prd}

## Topic
{topic}

---

## Your Failure Model

Review this document through the lens of system reliability, scalability, and
operational complexity. Flag:

- Missing SLAs, SLOs, or availability requirements
- Underspecified infrastructure decisions that will cause debates during sprint 1
- Security or compliance gaps (data residency, auth, secrets management)
- Architectural coupling that will create bottlenecks at scale
- Missing failure modes, fallback strategies, or graceful degradation paths

For each issue, cite the exact section where it appears or is absent.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the architectural gap or risk.",
    "section_ref": "§X.Y",
    "raised_by": "architect"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 6: Create prompts/prd_persona_scrum_master.md**

```markdown
You are a Certified Scrum Master and delivery lead with deep experience running
two-week sprints for product teams of 6-12 engineers.

## Document Under Review
{prd}

## Topic
{topic}

---

## Your Failure Model

Review this document for delivery risk and sprint-1 readiness. Flag:

- User stories or requirements that cannot be estimated without more information
- Missing acceptance criteria or "done" definitions
- Dependencies on external teams, vendors, or decisions that are not documented
- Requirements that will likely balloon in scope (creep risks)
- Missing sequencing: what must be built before what

For each issue, cite the exact section where it appears or is absent.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the delivery gap or dependency.",
    "section_ref": "§X.Y",
    "raised_by": "scrum_master"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 7: Create prompts/prd_persona_product_owner.md**

```markdown
You are a Product Owner with 10+ years of experience shipping B2B SaaS products.
You prioritize user value and ruthlessly defend scope.

## Document Under Review
{prd}

## Topic
{topic}

---

## Your Failure Model

Review this document from the perspective of user value, market fit, and scope
discipline. Flag:

- Features that have no clear user story or stakeholder benefit
- Missing prioritization (P0/P1/P2 or Must-Have / Should-Have / Could-Have)
- Scope inflation: nice-to-haves that have crept into the Must-Have tier
- Missing metrics for success — how will we know if this shipped?
- Gaps in user journey or role coverage (who does what, when, and why)

For each issue, cite the exact section where it appears or is absent.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the product gap or scope risk.",
    "section_ref": "§X.Y",
    "raised_by": "product_owner"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 8: Create prompts/generate_readme.md**

```markdown
You are a technical writer generating the README.md for a structured document package.

## Package Topic
{topic}

## Goal
{goal}

## Primary Artifact
{primary_artifact}

## Artifact Manifest
{artifact_manifest}

---

## Instructions

Generate a README.md that serves as the entry point for this document package.

Include:
1. A one-paragraph description of what this package is and what problem it solves
2. A "What It Contains" section listing the artifacts by layer with one-line descriptions
3. A "Quick Links by Audience" table (Leadership / Product / Engineering / Design)
   mapping each audience to which documents they should read first
4. A "Current Status" table showing each artifact's status

Write in crisp, professional Markdown. Output ONLY the README content.
No preamble or explanation.
```

- [ ] **Step 9: Create prompts/generate_docs_index.md**

```markdown
You are a technical writer generating the DOCS_INDEX.md for a structured document package.

## Package Topic
{topic}

## Goal
{goal}

## Primary Artifact
{primary_artifact}

## Artifact Manifest
{artifact_manifest}

## Review Personas Used
{personas}

---

## Instructions

Generate a DOCS_INDEX.md that serves as the canonical navigation map for
this document package. Include:

1. A package structure table (Layer / What it contains / Who reads it)
2. An "Authoritative Document" section pointing to {primary_artifact}
3. An "Execution Artifacts" section listing all execution-layer documents
   with purpose and who each is critical for
4. A "Companion Specs" section for companion-layer documents
5. "Recommended Reading Order" sections for each audience role
   (Leadership, Product, Architecture, Engineering, Design) with time estimates
6. A "Document Status Summary" table

Write in crisp, professional Markdown. Output ONLY the DOCS_INDEX content.
No preamble or explanation.
```

- [ ] **Step 10: Run a smoke test to confirm prompts load**

```bash
python -c "
from src.prompts import load_template
files = [
    'prd_builder.md', 'prd_challenger.md', 'prd_verify.md', 'prd_arbitrate.md',
    'prd_persona_architect.md', 'prd_persona_scrum_master.md',
    'prd_persona_product_owner.md', 'generate_readme.md', 'generate_docs_index.md',
]
for f in files:
    t = load_template(f)
    assert len(t) > 50, f'{f} looks empty'
    print(f'OK {f}')
print('All prompts load correctly.')
"
```
Expected: `OK` for each file, then `All prompts load correctly.`

- [ ] **Step 11: Commit**

```bash
git add prompts/prd_builder.md prompts/prd_challenger.md prompts/prd_verify.md \
        prompts/prd_arbitrate.md prompts/prd_persona_architect.md \
        prompts/prd_persona_scrum_master.md prompts/prd_persona_product_owner.md \
        prompts/generate_readme.md prompts/generate_docs_index.md
git commit -m "feat(prompts): add all 9 document-mode prompt files"
```

---

## Task 10: Config template

**Files:**
- Create: `configs/prd_template.yaml`

- [ ] **Step 1: Create configs/prd_template.yaml**

```yaml
# Document Mode Configuration Template
# Run with: autoresearch refine --config configs/prd_template.yaml

document:
  topic: "Your product or project name — PRD"
  goal: "Produce an execution-ready product requirements document"

  # Filename of the primary convergence target written to the output directory
  primary_artifact: PRD.md

  # Optional: path to raw notes, research findings, or prior draft
  # Passed to the Builder on cycle 1 as source material
  source_material: ""

  # How many consecutive clean cycles (0 valid + 0 human_required) before converging
  convergence_cycles: 1

  # Hard stop after N cycles regardless of convergence (0 = unlimited)
  max_cycles: 0

  # "parallel" runs all personas concurrently; "serial" runs them one at a time
  persona_mode: parallel

  # Reviewer personas — each maps to prompts/prd_persona_{name}.md
  personas:
    - name: architect        # Cloud architect — infra, scalability, security gaps
    - name: scrum_master     # Delivery risk — sprint-1 readiness, dependency mapping
    - name: product_owner    # User value, scope discipline, success metrics

  # Secondary artifacts generated after the primary artifact converges
  # Each maps to prompts/artifact_{stem}.md (where stem = name without .md)
  # review: true runs one Challenger + Persona + Verifier pass before writing
  artifacts:
    # --- Execution layer ---
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
    # --- Companion layer ---
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
    # Builder uses research[0], Challenger uses research[1]
    primary: claude             # Personas always use primary
    research: [codex, claude]   # research[0]=Builder, research[1]=Challenger
    judge: gemini               # Arbitrator
    utility: claude             # Verifier

  strategy_config:
    critique_depth: thorough    # "light" | "standard" | "thorough"
```

- [ ] **Step 2: Verify template loads cleanly**

```bash
python -c "
from src.config import DocumentConfig
from pathlib import Path
cfg = DocumentConfig.from_yaml(Path('configs/prd_template.yaml'))
print(f'topic: {cfg.topic}')
print(f'artifacts: {len(cfg.artifacts)}')
print(f'personas: {len(cfg.personas)}')
print(f'backends: primary={cfg.backends.primary}, research={cfg.backends.research}')
"
```
Expected output:
```
topic: Your product or project name — PRD
artifacts: 8
personas: 3
backends: primary=claude, research=('codex', 'claude')
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all tests PASS, no regressions.

- [ ] **Step 4: Commit**

```bash
git add configs/prd_template.yaml
git commit -m "feat(configs): add prd_template.yaml for document mode"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Covered by |
|---|---|
| `DocumentRefiner` sibling to `AutoResearcher` | Task 7 |
| `ConvergeStrategy` NOT a `Strategy` subclass | Task 5 (standalone class) |
| `BaseContext` extracted to `run_state.py` | Task 3 |
| `LoopContext` extends `BaseContext` | Task 3 |
| `CycleContext` extends `BaseContext` | Task 4 |
| `DocumentConfig` top-level `document:` key | Task 1 |
| `PersonaConfig`, `ArtifactConfig` | Task 1 |
| `Issue` with all fields | Task 4 |
| `CycleState` with HITL fields | Task 4 |
| `DeferReason`, `HumanInputRequest`, `HumanDecision` | Task 2 |
| `collect_interactive` — interactive HITL | Task 2 |
| `write_pending_questions` — async mode | Task 2 |
| `load_human_decisions` — resume | Task 2 |
| `run_builder` / `run_challenger` / `run_personas` | Task 5 |
| `run_verifier` classifies VALID/STALE/DEFER | Task 5 |
| `run_arbitrator` generates patches | Task 5 |
| Parallel persona execution (ThreadPoolExecutor) | Task 5 |
| Serial persona execution | Task 5 |
| Backend role convention (Builder=research[0], Challenger=research[1]) | Task 5 |
| `run_cycle` — full 5-step cycle | Task 6 |
| `_should_stop` convergence logic | Task 4 |
| `_update_convergence` — clean iff valid=0 AND human_required=0 | Task 4 |
| Issue registry with sequential IDs | Task 6 |
| Phase 1 convergence loop | Task 7 |
| Phase 2 expansion with optional review | Task 7 |
| Phase 3 README.md + DOCS_INDEX.md | Task 7 |
| `refine` CLI subcommand | Task 8 |
| `--no-interactive`, `--resume` flags | Task 8 |
| Non-zero exit on `human_required` in async mode | Task 7, Task 8 |
| Output structure: flat artifacts at root, `.run/` for machine data | Task 7 |
| `run_manifest.json`, `issue_registry.json`, cycle snapshots | Task 7 |
| Human decisions injected as ground truth block in Builder prompt | Task 5 (`_format_human_decisions`) |
| All 9 prompt files | Task 9 |
| `prd_template.yaml` | Task 10 |
| Existing research tests untouched | Task 3 (regression tested) |

### Placeholder scan

No TBD, TODO, or incomplete steps found. Every step contains complete code.

### Type consistency

All types used across tasks are consistent:
- `VerifiedCritique` uses `status: str` — matched in `run_cycle` (`v.status == "valid"`)
- `Patch` has `(section_ref, proposed_text, rationale)` — consistent in `_format_patches`
- `CycleContext` constructor args match `BaseContext(call_with, invoke_for_strategy, track_usage, track_cost)` + 4 document fields
- `DocumentRefiner._invoke(prompt, backend, backend_name)` matches `InvokeFn = Callable[[str, Backend, str], AgentResponse]` used by `ConvergeStrategy` methods
- `run_cycle` calls `strategy.run_builder(state.prd, patches, ctx.call_with, human_decisions=ctx.human_decisions)` — matches `ConvergeStrategy.run_builder(prd, patches, invoke, *, human_decisions)` signature

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-document-mode.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
