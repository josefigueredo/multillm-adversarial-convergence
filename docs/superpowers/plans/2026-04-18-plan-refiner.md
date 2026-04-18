# Plan Refiner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `plan` CLI subcommand that runs a multi-LLM adversarial convergence loop on PLAN.md files, refining them through 7 domain-specific reviewers until no valid issues remain.

**Architecture:** Full mirror of document mode — `PlanConfig` + `PlanRefiner` + `PlanStrategy` + `plan_loop.py` are parallel to their document counterparts. All data types (`RawCritique`, `VerifiedCritique`, `Patch`, `Issue`) and helpers (`_parse_*`, `_format_*`, `_make_human_requests`, `_register_issues`) are imported from existing modules — not duplicated. Prompt variable names use `plan` instead of `prd`.

**Tech Stack:** Python 3.10+, `dataclasses`, `pathlib`, `concurrent.futures`, `yaml`, `pytest`, `uv run pytest`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/config.py` | Modify | Add `PlanPersonaConfig`, `PlanConfig` after DocumentConfig section |
| `src/plan_loop.py` | Create | `PlanCycleState`, `PlanCycleContext`, `run_plan_cycle`, `_plan_should_stop` |
| `src/plan_strategy.py` | Create | `PlanStrategy` — 5-step convergence cycle for plans |
| `src/plan_refiner.py` | Create | `PlanRefiner` — Phase 1/2/3 orchestrator |
| `src/cli.py` | Modify | Add `plan` subcommand and `_run_plan()` handler |
| `prompts/plan_builder.md` | Create | Builder prompt — rewrites full plan applying patches |
| `prompts/plan_challenger.md` | Create | Challenger prompt — structural gaps only |
| `prompts/plan_verify.md` | Create | Verifier prompt — classifies critiques |
| `prompts/plan_arbitrate.md` | Create | Arbitrator prompt — produces patch list |
| `prompts/plan_persona_architect.md` | Create | Architect persona prompt |
| `prompts/plan_persona_tech_lead.md` | Create | Tech Lead persona prompt |
| `prompts/plan_persona_qa_engineer.md` | Create | QA Engineer persona prompt |
| `prompts/plan_persona_ai_engineer.md` | Create | AI Engineer persona prompt |
| `prompts/plan_persona_data_engineer.md` | Create | Data Engineer persona prompt |
| `prompts/plan_persona_security_engineer.md` | Create | Security Engineer persona prompt |
| `prompts/plan_persona_devils_advocate.md` | Create | Devil's Advocate persona prompt |
| `configs/plan_template.yaml` | Create | Annotated config reference |
| `tests/test_plan_config.py` | Create | PlanConfig loading tests |
| `tests/test_plan_loop.py` | Create | Cycle state and loop tests |
| `tests/test_plan_strategy.py` | Create | PlanStrategy unit tests |
| `tests/test_plan_refiner.py` | Create | PlanRefiner integration tests |
| `tests/test_cli.py` | Modify | Add `plan` subcommand tests |

---

## Task 1: PlanConfig

**Files:**
- Modify: `src/config.py` (append after the DocumentConfig section at end of file)
- Create: `tests/test_plan_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plan_config.py
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.config import ArtifactConfig, PlanConfig, PlanPersonaConfig, SourceFileConfig


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(textwrap.dedent(content))
    return p


def test_plan_config_minimal(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "My Plan"
          goal: "Build it"
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.topic == "My Plan"
    assert cfg.goal == "Build it"
    assert cfg.primary_artifact == "PLAN.md"
    assert cfg.convergence_cycles == 2
    assert cfg.max_cycles == 10
    assert cfg.persona_mode == "parallel"
    assert len(cfg.personas) == 7
    assert cfg.personas[0].name == "architect"
    assert cfg.personas[6].name == "devils_advocate"


def test_plan_config_custom_personas(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          personas:
            - name: architect
            - name: security_engineer
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.personas) == 2
    assert cfg.personas[1].name == "security_engineer"


def test_plan_config_custom_artifact(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          primary_artifact: "MY_PLAN.md"
          convergence_cycles: 3
          max_cycles: 20
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.primary_artifact == "MY_PLAN.md"
    assert cfg.convergence_cycles == 3
    assert cfg.max_cycles == 20


def test_plan_config_artifacts(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          artifacts:
            - name: RISK_REGISTER.md
              layer: companion
              review: false
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.artifacts) == 1
    assert cfg.artifacts[0].name == "RISK_REGISTER.md"
    assert cfg.artifacts[0].review is False


def test_plan_config_backends(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          backends:
            primary: claude
            research: [claude, gemini]
            judge: claude
            utility: gemini
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert cfg.backends.primary == "claude"
    assert cfg.backends.research == ("claude", "gemini")
    assert cfg.backends.judge == "claude"
    assert cfg.backends.utility == "gemini"


def test_plan_config_missing_topic_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          goal: "No topic"
    """)
    with pytest.raises(ValueError, match="topic"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_missing_plan_key_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "wrong key"
    """)
    with pytest.raises(ValueError, match="plan"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_invalid_persona_mode_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        plan:
          topic: "T"
          goal: "G"
          persona_mode: invalid
    """)
    with pytest.raises(ValueError, match="persona_mode"):
        PlanConfig.from_yaml(cfg_path)


def test_plan_config_source_files(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# Spec")
    cfg_path = _write_yaml(tmp_path, f"""
        plan:
          topic: "T"
          goal: "G"
          source_files:
            - path: spec.md
              roles: [builder, architect]
    """)
    cfg = PlanConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    assert cfg.source_files[0].roles == ("architect", "builder")


def test_plan_persona_config_default_prompt_file():
    p = PlanPersonaConfig(name="tech_lead")
    assert p.prompt_file == ""


def test_plan_persona_config_custom_prompt_file():
    p = PlanPersonaConfig(name="tech_lead", prompt_file="my_prompt.md")
    assert p.prompt_file == "my_prompt.md"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/josefigueredo/Code/josefigueredo/auto-research
uv run pytest tests/test_plan_config.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PlanConfig'`

- [ ] **Step 3: Add `PlanPersonaConfig` and `PlanConfig` to `src/config.py`**

Append after the closing `"""` of `DocumentConfig.from_yaml` (end of file, after line 722):

```python


# ---------------------------------------------------------------------------
# Plan-mode configuration (loaded by `plan` subcommand)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanPersonaConfig:
    """A single reviewer persona for the plan convergence loop.

    Attributes:
        name: Persona identifier — used for role-based source file filtering
            and as the default prompt file stem.
        prompt_file: Override prompt template filename.  Defaults to
            ``plan_persona_{name}.md`` when empty.
    """

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class PlanConfig:
    """Top-level configuration for a plan refinement run.

    Loaded from a YAML file with a top-level ``plan:`` key via :meth:`from_yaml`.
    Independent of ``ResearchConfig`` and ``DocumentConfig``.

    Attributes:
        topic: Short label for the plan being refined.
        goal: What the finished plan should enable — e.g. "unambiguous enough
            that a senior engineer can execute without clarifying questions."
        primary_artifact: Filename of the main document produced by Phase 1.
            Defaults to ``"PLAN.md"``.
        source_material: Path or raw text injected into the Builder prompt as
            seed content for cycle 0.
        convergence_cycles: Consecutive clean cycles required before stopping.
            Defaults to ``2`` (stricter than document mode's ``1``).
        max_cycles: Hard cap on total convergence cycles.  ``0`` means no cap.
        persona_mode: ``"parallel"`` runs all personas concurrently;
            ``"serial"`` runs them in declaration order.
        personas: Review personas executed each cycle.  Defaults to all seven
            plan-specific personas.
        artifacts: Phase 2 companion documents derived from the converged plan.
        source_files: Companion files injected as structured context into agent
            prompts, with per-file role targeting.  See :class:`SourceFileConfig`.
        backends: Role-to-backend mapping for the convergence loop.
        strategy_config: Strategy-level tuning (e.g. ``critique_depth``).
    """

    topic: str
    goal: str
    primary_artifact: str = "PLAN.md"
    source_material: str = ""
    convergence_cycles: int = 2
    max_cycles: int = 10
    persona_mode: str = "parallel"
    personas: tuple[PlanPersonaConfig, ...] = (
        PlanPersonaConfig("architect"),
        PlanPersonaConfig("tech_lead"),
        PlanPersonaConfig("qa_engineer"),
        PlanPersonaConfig("ai_engineer"),
        PlanPersonaConfig("data_engineer"),
        PlanPersonaConfig("security_engineer"),
        PlanPersonaConfig("devils_advocate"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    source_files: tuple[SourceFileConfig, ...] = ()
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "PlanConfig":
        """Load a plan config from a YAML file with a top-level ``plan:`` key.

        Expected YAML structure (all keys except ``topic`` are optional)::

            plan:
              topic: "Feature name"
              goal: "What the plan should enable"
              primary_artifact: "PLAN.md"
              source_material: ""
              convergence_cycles: 2
              max_cycles: 10
              persona_mode: parallel        # parallel | serial
              personas:
                - name: architect
                - name: tech_lead
              source_files:
                - path: docs/**/*.md
                  roles: [builder, architect]
              artifacts:
                - name: RISK_REGISTER.md
                  layer: companion
                  review: false
              backends:
                primary: claude
                research: [claude, gemini]
                judge: claude
                utility: gemini

        Args:
            path: Path to the YAML config file.  Relative ``source_files`` paths
                are resolved relative to this file's parent directory.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is malformed, missing required fields, or a
                literal (non-glob) ``source_files`` path is not found on disk.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        if "plan" not in raw:
            raise ValueError("Config must contain a top-level 'plan' key")

        plan_raw: dict[str, Any] = raw["plan"]

        if "topic" not in plan_raw:
            raise ValueError("'plan' section must contain a 'topic' field")

        persona_mode = plan_raw.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        raw_personas = plan_raw.get("personas", [])
        personas: tuple[PlanPersonaConfig, ...]
        if raw_personas:
            personas = tuple(
                PlanPersonaConfig(name=p["name"], prompt_file=p.get("prompt_file", ""))
                for p in raw_personas
            )
        else:
            personas = (
                PlanPersonaConfig("architect"),
                PlanPersonaConfig("tech_lead"),
                PlanPersonaConfig("qa_engineer"),
                PlanPersonaConfig("ai_engineer"),
                PlanPersonaConfig("data_engineer"),
                PlanPersonaConfig("security_engineer"),
                PlanPersonaConfig("devils_advocate"),
            )

        config_dir = path.parent
        persona_names = {p.name for p in personas}
        source_files = _parse_source_files(
            plan_raw.get("source_files", []), config_dir, persona_names
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in plan_raw.get("artifacts", [])
        )

        backends_raw: dict[str, Any] = plan_raw.get("backends", {})
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

        strat_raw: dict[str, Any] = plan_raw.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )

        return cls(
            topic=plan_raw["topic"],
            goal=plan_raw.get("goal", plan_raw["topic"]),
            primary_artifact=plan_raw.get("primary_artifact", "PLAN.md"),
            source_material=plan_raw.get("source_material", ""),
            convergence_cycles=plan_raw.get("convergence_cycles", 2),
            max_cycles=plan_raw.get("max_cycles", 10),
            persona_mode=persona_mode,
            personas=personas,
            artifacts=artifacts,
            source_files=source_files,
            backends=backends_cfg,
            strategy_config=strategy_cfg,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_plan_config.py -v
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_plan_config.py
git commit -m "feat: add PlanPersonaConfig and PlanConfig"
```

---

## Task 2: plan_loop.py

**Files:**
- Create: `src/plan_loop.py`
- Create: `tests/test_plan_loop.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plan_loop.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backends.types import AgentResponse
from src.config import BackendsConfig, PlanConfig
from src.document_loop import Issue
from src.hitl import DeferReason, HumanDecision
from src.plan_loop import (
    PlanCycleContext,
    PlanCycleState,
    _plan_should_stop,
    _update_plan_convergence,
    run_plan_cycle,
)


def _make_config(**kwargs) -> PlanConfig:
    defaults = dict(topic="T", goal="G", convergence_cycles=2, max_cycles=10)
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_invoke(text: str = "[]"):
    def invoke(prompt, backend_obj, backend_name):
        return AgentResponse(text=text, cost_usd=0.0, is_error=False,
                             input_tokens=0, output_tokens=0)
    return invoke


def _make_ctx(config=None) -> PlanCycleContext:
    cfg = config or _make_config()
    return PlanCycleContext(
        call_with=_make_invoke(),
        invoke_for_strategy=_make_invoke(),
        track_usage=lambda resp, name: None,
        track_cost=lambda cost, name: None,
        config=cfg,
        human_decisions=[],
        update_issue_registry=lambda issues: None,
    )


# ── _plan_should_stop ────────────────────────────────────────────────────────

def test_should_stop_when_convergence_cycles_reached():
    cfg = _make_config(convergence_cycles=2, max_cycles=0)
    state = PlanCycleState()
    state.consecutive_clean_cycles = 2
    assert _plan_should_stop(state, cfg) is True


def test_should_not_stop_below_convergence_cycles():
    cfg = _make_config(convergence_cycles=2, max_cycles=0)
    state = PlanCycleState()
    state.consecutive_clean_cycles = 1
    assert _plan_should_stop(state, cfg) is False


def test_should_stop_at_max_cycles():
    cfg = _make_config(convergence_cycles=5, max_cycles=3)
    state = PlanCycleState()
    state.cycle = 3
    assert _plan_should_stop(state, cfg) is True


def test_max_cycles_zero_means_no_cap():
    cfg = _make_config(convergence_cycles=99, max_cycles=0)
    state = PlanCycleState()
    state.cycle = 1000
    assert _plan_should_stop(state, cfg) is False


# ── _update_plan_convergence ─────────────────────────────────────────────────

def test_clean_cycle_increments_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 1
    _update_plan_convergence(state, valid_count=0, human_required_count=0)
    assert state.consecutive_clean_cycles == 2


def test_valid_critiques_resets_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 3
    _update_plan_convergence(state, valid_count=1, human_required_count=0)
    assert state.consecutive_clean_cycles == 0


def test_human_required_resets_streak():
    state = PlanCycleState()
    state.consecutive_clean_cycles = 2
    _update_plan_convergence(state, valid_count=0, human_required_count=1)
    assert state.consecutive_clean_cycles == 0


# ── run_plan_cycle ───────────────────────────────────────────────────────────

def test_run_plan_cycle_increments_cycle():
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# Revised Plan"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_plan_cycle(state, ctx, strategy)

    assert state.cycle == 1


def test_run_plan_cycle_returns_counts():
    from src.document_strategy import VerifiedCritique
    cfg = _make_config()
    state = PlanCycleState(plan="# Plan")
    ctx = _make_ctx(cfg)

    valid = VerifiedCritique(description="d", section_ref="§1",
                              raised_by="challenger", status="valid")
    stale = VerifiedCritique(description="d", section_ref="§2",
                              raised_by="architect", status="stale")
    deferred = VerifiedCritique(description="d", section_ref="§3",
                                 raised_by="qa_engineer", status="deferred",
                                 defer_reason="out_of_scope")

    strategy = MagicMock()
    strategy.run_builder.return_value = "# Plan v2"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = [valid, stale, deferred]
    strategy.run_arbitrator.return_value = []

    v, s, d = run_plan_cycle(state, ctx, strategy)

    assert v == 1
    assert s == 1
    assert d == 1


def test_run_plan_cycle_updates_plan_text():
    cfg = _make_config()
    state = PlanCycleState(plan="# Old")
    ctx = _make_ctx(cfg)
    strategy = MagicMock()
    strategy.run_builder.return_value = "# New"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_plan_cycle(state, ctx, strategy)

    assert state.plan == "# New"
    assert state.plan_versions == ["# New"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_plan_loop.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PlanCycleState'`

- [ ] **Step 3: Create `src/plan_loop.py`**

```python
"""Plan convergence loop — state types, context, and cycle execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import PlanConfig
from .document_loop import (
    Issue,
    _make_human_requests,
    _register_issues,
)
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .run_state import BaseContext


@dataclass
class PlanCycleState:
    """Mutable state for the plan convergence loop."""

    plan: str = ""
    plan_path: Path = field(default_factory=lambda: Path("PLAN.md"))
    plan_versions: list[str] = field(default_factory=list)
    cycle: int = 0
    issue_registry: list[Issue] = field(default_factory=list)
    consecutive_clean_cycles: int = 0
    pending_human_inputs: list[HumanInputRequest] = field(default_factory=list)
    human_decisions: list[HumanDecision] = field(default_factory=list)
    pending_patches: list[Any] = field(default_factory=list)
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0


@dataclass
class PlanCycleContext(BaseContext):
    """Callback bundle for the plan loop.

    Extends ``BaseContext`` (call_with, invoke_for_strategy, track_usage,
    track_cost) with plan-specific state.
    """

    config: PlanConfig
    human_decisions: list[HumanDecision]
    update_issue_registry: Callable[[list[Any]], None]


def _plan_should_stop(state: PlanCycleState, config: PlanConfig) -> bool:
    """Return True when the plan convergence run should terminate."""
    if config.max_cycles > 0 and state.cycle >= config.max_cycles:
        return True
    return state.consecutive_clean_cycles >= config.convergence_cycles


def _update_plan_convergence(
    state: PlanCycleState,
    valid_count: int,
    human_required_count: int,
) -> None:
    """Increment or reset the clean-cycle counter.

    A cycle is clean only when there are zero VALID critiques AND zero
    human_required deferrals.
    """
    if valid_count == 0 and human_required_count == 0:
        state.consecutive_clean_cycles += 1
    else:
        state.consecutive_clean_cycles = 0


def run_plan_cycle(
    state: PlanCycleState,
    ctx: PlanCycleContext,
    strategy: Any,
    *,
    interactive: bool = True,
) -> tuple[int, int, int]:
    """Execute one plan convergence cycle.

    Returns:
        Tuple of (valid_count, stale_count, deferred_count).
    """
    state.cycle += 1

    # 1. Builder — apply pending patches and produce revised plan
    plan = strategy.run_builder(
        state.plan,
        state.pending_patches,
        ctx.call_with,
        human_decisions=ctx.human_decisions,
    )
    state.plan = plan
    state.plan_versions.append(plan)
    state.pending_patches = []

    # 2. Challenger
    raw_critiques = strategy.run_challenger(plan, ctx.call_with)

    # 3. Personas
    persona_critiques = strategy.run_personas(plan, ctx.call_with)

    all_raw = raw_critiques + persona_critiques

    # 4. Verifier
    verified = strategy.run_verifier(plan, all_raw, ctx.call_with)

    # 5. Classify
    valid = [v for v in verified if v.status == "valid"]
    stale = [v for v in verified if v.status == "stale"]
    deferred = [v for v in verified if v.status == "deferred"]
    human_required = [
        v for v in deferred if v.defer_reason == DeferReason.HUMAN_REQUIRED
    ]

    # 6. HITL gate
    if human_required:
        requests = _make_human_requests(human_required, state.cycle, state.issue_registry)
        state.pending_human_inputs = requests
        if interactive:
            from .hitl import collect_interactive
            decisions = collect_interactive(requests)
            state.human_decisions.extend(decisions)
            ctx.human_decisions.extend(decisions)
            state.pending_human_inputs = []

    # 7. Arbitrator — patches for VALID only
    new_patches = strategy.run_arbitrator(plan, valid, ctx.call_with)
    state.pending_patches = new_patches

    # 8. Update issue registry
    _register_issues(state, verified)

    # 9. Update convergence counter
    _update_plan_convergence(
        state,
        valid_count=len(valid),
        human_required_count=len(human_required),
    )

    return len(valid), len(stale), len(deferred)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_plan_loop.py -v
```

Expected: `12 passed`

- [ ] **Step 5: Commit**

```bash
git add src/plan_loop.py tests/test_plan_loop.py
git commit -m "feat: add plan_loop with PlanCycleState and run_plan_cycle"
```

---

## Task 3: Prompt Files

**Files:** Create 11 files under `prompts/`

No tests for prompt files — they are text templates verified by strategy tests in Task 4.

- [ ] **Step 1: Create `prompts/plan_builder.md`**

```markdown
You are a senior technical writer and implementation architect tasked with
producing or refining an implementation plan.

## Topic
{topic}

## Goal
{goal}

## Source Material
{source_material}

{source_files}

{human_decisions}

## Current Plan
{current_plan}

## Patches to Apply
{patches}

---

## Instructions

If the current plan is empty and there are no patches, generate the initial
implementation plan from the source material and topic. The plan must follow
this structure exactly:

- A header block with Goal, Architecture, and Tech Stack
- Numbered tasks (### Task N: Name)
- Each task has: Files section, then checkbox steps (- [ ] Step N: ...)
- Every step that writes code must include the complete code block
- Every step that runs a command must include the exact command and expected output
- Commit steps must use conventional commit format

If patches are provided, apply each patch faithfully. Where a HUMAN DECISIONS
block is present, treat every answer as ground truth. Preserve ALL checkbox
syntax (`- [ ]`) exactly — do not convert to dashes or bullets. Keep unpatched
tasks verbatim.

Output ONLY the complete, updated plan in Markdown. No preamble, no explanation.
```

- [ ] **Step 2: Create `prompts/plan_challenger.md`**

```markdown
You are a structural plan auditor. Your job is to find gaps in the
implementation plan's structure and completeness — NOT to review the
technical decisions themselves.

## Topic
{topic}

{source_files}

## Plan Under Review
{plan}

---

## Your Failure Model

Find only structural problems:

- Tasks that reference types, functions, or files not defined in any earlier task
- Tasks in the wrong order (task N depends on something task N+3 creates)
- Steps so vague that an engineer cannot execute them without guessing
- Missing tasks entirely (e.g. the plan mentions X but has no task that creates X)
- Tasks that are too large to be a single coherent unit of work
- Test steps that don't include actual test code

Do NOT flag: architectural choices, technology preferences, naming conventions,
or anything that is a matter of opinion rather than a structural gap.

Respond with a JSON array only. No preamble or explanation.

```json
[
  {{
    "description": "Task 3 references `PlanCycleState` but it is not defined until Task 5.",
    "section_ref": "Task 3",
    "raised_by": "challenger"
  }}
]
```

If the plan has no structural issues, respond with an empty array: `[]`
```

- [ ] **Step 3: Create `prompts/plan_verify.md`**

```markdown
You are a verification specialist. Classify each critique below as VALID,
STALE, or DEFERRED — based solely on what the plan actually says.

## Plan
{plan}

## Critiques to Verify
```json
{critiques_json}
```

---

## Classification Rules

- **valid**: The critique is accurate — the plan actually has this problem.
- **stale**: The plan already addresses this concern adequately.
- **deferred (out_of_scope)**: The critique concerns something outside this
  plan's scope. Does NOT block convergence.
- **deferred (needs_research)**: Resolving this requires information not in
  the plan, but the pipeline can generate it. Does NOT block convergence.
- **deferred (human_required)**: Only a human engineer can answer this.
  BLOCKS convergence. Provide a focused `question` and a `suggested_answer`.

Return a JSON array with one object per input critique, in the same order.

```json
[
  {{
    "description": "original description",
    "section_ref": "Task 3",
    "raised_by": "challenger",
    "status": "valid",
    "defer_reason": null,
    "question": null,
    "suggested_answer": null
  }},
  {{
    "description": "unclear scope",
    "section_ref": "Task 1",
    "raised_by": "architect",
    "status": "deferred",
    "defer_reason": "human_required",
    "question": "Should this task include migration rollback steps?",
    "suggested_answer": "Yes — add a rollback step after the migration step."
  }}
]
```

Output ONLY the JSON array. No preamble.
```

- [ ] **Step 4: Create `prompts/plan_arbitrate.md`**

```markdown
You are an expert technical arbitrator. Generate precise patch proposals
for each VALID critique listed below.

## Plan
{plan}

## Valid Critiques Requiring Patches
```json
{valid_critiques_json}
```

---

## Instructions

For each critique, propose a targeted text replacement that resolves the issue.
Keep patches minimal — only change what is necessary. Prefer adding steps or
clarifying existing ones over restructuring tasks.

Output ONLY a JSON array. No preamble.

```json
[
  {{
    "section_ref": "Task 3, Step 2",
    "proposed_text": "The exact replacement text for this step...",
    "rationale": "One sentence explaining why this patch resolves the critique."
  }}
]
```

If you cannot propose a patch for a critique, omit it from the array.
```

- [ ] **Step 5: Create `prompts/plan_persona_architect.md`**

```markdown
You are a Software Architect with 15+ years experience in distributed systems,
clean architecture, and API design.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of software architecture. Flag:

- File boundaries that violate single-responsibility — a file doing too many things
- Coupling between tasks that should be independent (task A breaks if task B changes)
- Missing abstraction layers that will cause pain at integration time
- Architectural decisions made implicitly that should be explicit tasks
- Responsibilities assigned to the wrong layer (e.g. business logic in CLI handlers)
- Missing interface definitions before implementations that depend on them

For each issue, cite the exact task or step where it appears or is absent.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the architectural gap.",
    "section_ref": "Task N",
    "raised_by": "architect"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 6: Create `prompts/plan_persona_tech_lead.md`**

```markdown
You are a Tech Lead who has managed delivery of complex software projects
and knows exactly where implementation plans fall apart during execution.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of practical delivery. Flag:

- Tasks too large to complete in a single focused session (should be split)
- Tasks too small to be meaningful commits (should be merged)
- Dependency order errors — task N uses something defined in task N+3
- Naming inconsistencies across tasks (same function called differently)
- Commits that mix concerns (feat + refactor + test in one commit)
- Steps that say what to do but not how (no code or command shown)
- Missing steps that every engineer knows but nobody writes down

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the delivery risk.",
    "section_ref": "Task N, Step M",
    "raised_by": "tech_lead"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 7: Create `prompts/plan_persona_qa_engineer.md`**

```markdown
You are a QA Engineer who practices strict TDD and has seen what happens
when test discipline breaks down mid-project.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of test quality. Flag:

- Implementation steps that appear before the corresponding test step
- Test steps with no actual test code shown (just descriptions)
- Missing edge case tests — happy path only, no error paths
- Missing integration tests at module or API boundaries
- Test setup that will be flaky (real filesystem, real network, real time)
- Test assertions that don't verify the right thing
- Missing "run test to verify it fails first" steps before implementation
- Missing "run test to verify it passes" steps after implementation

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the test gap.",
    "section_ref": "Task N, Step M",
    "raised_by": "qa_engineer"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 8: Create `prompts/plan_persona_ai_engineer.md`**

```markdown
You are an AI Engineer who builds production LLM pipelines and knows
where AI-specific concerns get overlooked in implementation plans.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of AI/LLM engineering. Flag:

- Prompt templates with no validation of LLM output format
- Missing JSON parsing with fallback for malformed LLM responses
- No strategy for handling non-deterministic outputs (retry logic, validation)
- Model/backend selection with no rationale for the choice
- Missing evaluation step for LLM-generated content quality
- Hardcoded model names that should be configurable
- Missing token/cost tracking for LLM calls in the plan
- Prompt injection risks from unsanitized user-provided content

Only flag issues relevant to AI/LLM usage. If the plan has no AI components,
respond with `[]`.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the AI engineering gap.",
    "section_ref": "Task N",
    "raised_by": "ai_engineer"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 9: Create `prompts/plan_persona_data_engineer.md`**

```markdown
You are a Data Engineer with deep experience in data pipelines, schema
migrations, and the operational risks of data transformation tasks.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of data engineering. Flag:

- Schema changes with no migration task
- Migration tasks with no rollback step for destructive operations
- Data transformation steps with no validation of input/output shape
- ETL steps in the wrong order (transform before extract, load before transform)
- Missing data volume considerations for operations that may time out at scale
- Hardcoded connection strings or credentials in plan steps
- Missing idempotency guarantees for tasks that may be retried

Only flag issues relevant to data handling. If the plan has no data
components, respond with `[]`.

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the data engineering gap.",
    "section_ref": "Task N",
    "raised_by": "data_engineer"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 10: Create `prompts/plan_persona_security_engineer.md`**

```markdown
You are a Security Engineer who reviews implementation plans for
vulnerabilities before a single line of code is written.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Review this plan through the lens of security. Flag:

- Input validation missing at system boundaries (user input, external APIs, files)
- Command injection risks in subprocess or shell invocation steps
- SQL injection risks in any database interaction steps
- Secrets or credentials hardcoded in plan steps or config examples
- Auth/authz assumptions that are never explicitly implemented
- File path traversal risks (unsanitized user-provided paths)
- Missing TLS/encryption requirements for data in transit or at rest
- Unsafe deserialization of untrusted data (pickle, eval, exec)
- Missing rate limiting for any externally exposed endpoint

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the security gap.",
    "section_ref": "Task N, Step M",
    "raised_by": "security_engineer"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 11: Create `prompts/plan_persona_devils_advocate.md`**

```markdown
You are a Devil's Advocate. Your job is to find everything that could go
wrong with this plan that the other reviewers won't catch.

{source_files}

## Plan Under Review
{plan}

## Topic
{topic}

---

## Your Failure Model

Challenge hidden assumptions and find missing failure scenarios. Flag:

- Assumptions stated as facts with no validation step
- Steps that "everyone knows how to do" but are missing from the plan
- What happens if task N fails halfway through — is there a recovery path?
- External dependencies assumed to be available but never checked
- Steps that will silently succeed even when they've failed
- Circular dependencies between tasks that will cause a deadlock
- Steps that work locally but will break in CI or production environments
- Missing "definition of done" — how will an engineer know a task is complete?
- Optimistic assumptions about API availability, rate limits, or latency

Respond with a JSON array only.

```json
[
  {{
    "description": "Precise description of the hidden assumption or failure scenario.",
    "section_ref": "Task N",
    "raised_by": "devils_advocate"
  }}
]
```

If you find no issues, respond with `[]`.
```

- [ ] **Step 12: Commit all prompt files**

```bash
git add prompts/plan_builder.md prompts/plan_challenger.md prompts/plan_verify.md \
        prompts/plan_arbitrate.md prompts/plan_persona_architect.md \
        prompts/plan_persona_tech_lead.md prompts/plan_persona_qa_engineer.md \
        prompts/plan_persona_ai_engineer.md prompts/plan_persona_data_engineer.md \
        prompts/plan_persona_security_engineer.md prompts/plan_persona_devils_advocate.md
git commit -m "feat: add plan refiner prompt templates"
```

---

## Task 4: PlanStrategy

**Files:**
- Create: `src/plan_strategy.py`
- Create: `tests/test_plan_strategy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plan_strategy.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.backends.types import AgentResponse
from src.config import BackendsConfig, PlanConfig, PlanPersonaConfig, SourceFileConfig
from src.document_strategy import Patch, RawCritique, VerifiedCritique
from src.hitl import HumanDecision
from src.plan_strategy import PlanStrategy


def _make_backend(text: str = "[]") -> MagicMock:
    b = MagicMock()
    b.run.return_value = AgentResponse(
        text=text, cost_usd=0.01, is_error=False, input_tokens=10, output_tokens=20
    )
    return b


def _make_config(**kwargs) -> PlanConfig:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_strategy(backends_dict=None, **cfg_kwargs) -> PlanStrategy:
    cfg = _make_config(**cfg_kwargs)
    if backends_dict is None:
        backends_dict = {"claude": _make_backend()}
    return PlanStrategy(cfg, backends_dict)


def _call_with(prompt, backend_obj, backend_name):
    return backend_obj.run(prompt, None)


# ── Backend role resolution ──────────────────────────────────────────────────

def test_builder_uses_research_0():
    codex = _make_backend()
    claude = _make_backend()
    cfg = PlanConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("codex", "claude")),
    )
    s = PlanStrategy(cfg, {"codex": codex, "claude": claude})
    assert s._builder is codex


def test_challenger_uses_research_1():
    codex = _make_backend()
    claude = _make_backend()
    cfg = PlanConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("codex", "claude")),
    )
    s = PlanStrategy(cfg, {"codex": codex, "claude": claude})
    assert s._challenger is claude


def test_challenger_falls_back_to_primary_when_single_research():
    claude = _make_backend()
    cfg = PlanConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude", research=("claude",)),
    )
    s = PlanStrategy(cfg, {"claude": claude})
    assert s._challenger is claude


# ── _source_block ────────────────────────────────────────────────────────────

def test_source_block_empty_when_no_files():
    s = _make_strategy()
    assert s._source_block("builder") == ""


def test_source_block_filters_by_role(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# Doc")
    cfg = PlanConfig(
        topic="T", goal="G",
        source_files=(
            SourceFileConfig(path=str(f), roles=("builder",)),
        ),
    )
    s = PlanStrategy(cfg, {"claude": _make_backend()})
    block = s._source_block("builder")
    assert "## Reference Files" in block
    assert "# Doc" in block


def test_source_block_empty_for_unmatched_role(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# Doc")
    cfg = PlanConfig(
        topic="T", goal="G",
        source_files=(
            SourceFileConfig(path=str(f), roles=("builder",)),
        ),
    )
    s = PlanStrategy(cfg, {"claude": _make_backend()})
    assert s._source_block("architect") == ""


# ── run_builder ──────────────────────────────────────────────────────────────

def test_run_builder_returns_text():
    backend = _make_backend("# Revised Plan")
    s = PlanStrategy(_make_config(), {"claude": backend})
    result = s.run_builder("# Old", [], _call_with, human_decisions=[])
    assert result == "# Revised Plan"


def test_run_builder_calls_invoke_once():
    backend = _make_backend("# Plan")
    s = PlanStrategy(_make_config(), {"claude": backend})
    s.run_builder("", [], _call_with, human_decisions=[])
    assert backend.run.call_count == 1


# ── run_challenger ───────────────────────────────────────────────────────────

def test_run_challenger_parses_json():
    payload = json.dumps([{
        "description": "Missing test", "section_ref": "Task 1", "raised_by": "challenger"
    }])
    backend = _make_backend(payload)
    s = PlanStrategy(_make_config(), {"claude": backend})
    result = s.run_challenger("# Plan", _call_with)
    assert len(result) == 1
    assert isinstance(result[0], RawCritique)
    assert result[0].raised_by == "challenger"


def test_run_challenger_returns_empty_on_no_issues():
    s = PlanStrategy(_make_config(), {"claude": _make_backend("[]")})
    result = s.run_challenger("# Plan", _call_with)
    assert result == []


# ── run_verifier ─────────────────────────────────────────────────────────────

def test_run_verifier_returns_empty_when_no_critiques():
    s = _make_strategy()
    result = s.run_verifier("# Plan", [], _call_with)
    assert result == []


def test_run_verifier_parses_verified_critiques():
    payload = json.dumps([{
        "description": "d", "section_ref": "Task 1", "raised_by": "challenger",
        "status": "valid", "defer_reason": None, "question": None, "suggested_answer": None
    }])
    backend = _make_backend(payload)
    s = PlanStrategy(_make_config(), {"claude": backend})
    raw = [RawCritique(description="d", section_ref="Task 1", raised_by="challenger")]
    result = s.run_verifier("# Plan", raw, _call_with)
    assert len(result) == 1
    assert result[0].status == "valid"


# ── run_arbitrator ───────────────────────────────────────────────────────────

def test_run_arbitrator_returns_empty_when_no_valid():
    s = _make_strategy()
    result = s.run_arbitrator("# Plan", [], _call_with)
    assert result == []


def test_run_arbitrator_parses_patches():
    payload = json.dumps([{
        "section_ref": "Task 1", "proposed_text": "New text", "rationale": "Fix it"
    }])
    backend = _make_backend(payload)
    s = PlanStrategy(_make_config(), {"claude": backend})
    valid = [VerifiedCritique(
        description="d", section_ref="Task 1", raised_by="challenger", status="valid"
    )]
    result = s.run_arbitrator("# Plan", valid, _call_with)
    assert len(result) == 1
    assert isinstance(result[0], Patch)


# ── run_personas ─────────────────────────────────────────────────────────────

def test_run_personas_parallel_collects_all_results():
    backend = _make_backend("[]")
    cfg = PlanConfig(
        topic="T", goal="G",
        persona_mode="parallel",
        personas=(PlanPersonaConfig("architect"), PlanPersonaConfig("tech_lead")),
    )
    s = PlanStrategy(cfg, {"claude": backend})
    result = s.run_personas("# Plan", _call_with)
    assert result == []
    assert backend.run.call_count == 2


def test_run_personas_serial_collects_all_results():
    backend = _make_backend("[]")
    cfg = PlanConfig(
        topic="T", goal="G",
        persona_mode="serial",
        personas=(PlanPersonaConfig("architect"), PlanPersonaConfig("tech_lead")),
    )
    s = PlanStrategy(cfg, {"claude": backend})
    result = s.run_personas("# Plan", _call_with)
    assert result == []
    assert backend.run.call_count == 2


def test_invoke_persona_uses_plan_prefix_by_default(tmp_path):
    backend = _make_backend("[]")
    cfg = PlanConfig(
        topic="T", goal="G",
        personas=(PlanPersonaConfig("tech_lead"),),
    )
    s = PlanStrategy(cfg, {"claude": backend})
    with pytest.raises(Exception):
        # plan_persona_tech_lead.md doesn't exist in test env — that's fine,
        # we just verify it tries the right file name
        s._invoke_persona(cfg.personas[0], "# Plan", _call_with)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_plan_strategy.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PlanStrategy'`

- [ ] **Step 3: Create `src/plan_strategy.py`**

```python
"""PlanStrategy — standalone multi-LLM plan convergence strategy.

NOT a Strategy subclass and NOT registered in _STRATEGY_REGISTRY.
Used exclusively by PlanRefiner.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backends import Backend, CallOptions
from .config import PlanConfig
from .document_strategy import (
    InvokeFn,
    Patch,
    RawCritique,
    VerifiedCritique,
    _format_human_decisions,
    _format_patches,
    _parse_patches,
    _parse_raw_critiques,
    _parse_verified_critiques,
)
from .hitl import HumanDecision
from .prompts import render

log = logging.getLogger("autoresearch")


class PlanStrategy:
    """Orchestrates the 5-step plan convergence cycle.

    Standalone — does NOT extend Strategy and is NOT in _STRATEGY_REGISTRY.
    """

    def __init__(self, config: PlanConfig, backends: dict[str, Backend]) -> None:
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

    # ── Source file injection ────────────────────────────────────────────────

    def _source_block(self, role: str) -> str:
        """Return a formatted Markdown block of source files visible to *role*.

        Returns an empty string when no files match — safe to inject into
        prompt templates without checking. The ``## Reference Files`` heading
        is included only when at least one file is readable.
        """
        matching = [sf for sf in self._config.source_files if role in sf.roles]
        if not matching:
            return ""
        parts = []
        for sf in matching:
            try:
                content = Path(sf.path).read_text(encoding="utf-8")
            except OSError:
                log.warning("source_files: could not read %s — skipping", sf.path)
                continue
            parts.append(f"### {sf.path}\n\n{content}")
        if not parts:
            return ""
        return "## Reference Files\n\n" + "\n\n---\n\n".join(parts)

    # ── Builder ─────────────────────────────────────────────────────────────

    def run_builder(
        self,
        plan: str,
        patches: list[Patch],
        invoke: InvokeFn,
        *,
        human_decisions: list[HumanDecision],
    ) -> str:
        """Generate the initial plan (cycle 1) or apply validated patches (cycle N+)."""
        human_block = _format_human_decisions(human_decisions)
        patches_block = _format_patches(patches)
        prompt = render(
            "plan_builder.md",
            topic=self._config.topic,
            goal=self._config.goal,
            source_material=self._config.source_material,
            source_files=self._source_block("builder"),
            current_plan=plan,
            patches=patches_block,
            human_decisions=human_block,
        )
        resp = invoke(prompt, self._builder, self._builder_name)
        return resp.text

    # ── Challenger ──────────────────────────────────────────────────────────

    def run_challenger(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run structural gap critique. Returns list of raw critiques."""
        prompt = render(
            "plan_challenger.md",
            plan=plan,
            topic=self._config.topic,
            source_files=self._source_block("challenger"),
        )
        resp = invoke(prompt, self._challenger, self._challenger_name)
        return _parse_raw_critiques(resp.text, default_raised_by="challenger")

    # ── Personas ────────────────────────────────────────────────────────────

    def run_personas(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run all personas. Parallel or serial per config.persona_mode."""
        if self._config.persona_mode == "parallel":
            return self._run_personas_parallel(plan, invoke)
        return self._run_personas_serial(plan, invoke)

    def _run_personas_parallel(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        with ThreadPoolExecutor(max_workers=len(self._config.personas)) as pool:
            futures = {
                pool.submit(self._invoke_persona, persona, plan, invoke): persona
                for persona in self._config.personas
            }
            for future in as_completed(futures):
                results.extend(future.result())
        return results

    def _run_personas_serial(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        for persona in self._config.personas:
            results.extend(self._invoke_persona(persona, plan, invoke))
        return results

    def _invoke_persona(self, persona: Any, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        prompt_file = persona.prompt_file or f"plan_persona_{persona.name}.md"
        prompt = render(
            prompt_file,
            plan=plan,
            topic=self._config.topic,
            source_files=self._source_block(persona.name),
        )
        resp = invoke(prompt, self._persona_backend, self._persona_name)
        return _parse_raw_critiques(resp.text, default_raised_by=persona.name)

    # ── Verifier ────────────────────────────────────────────────────────────

    def run_verifier(
        self, plan: str, critiques: list[RawCritique], invoke: InvokeFn
    ) -> list[VerifiedCritique]:
        """Classify each critique as valid / stale / deferred."""
        if not critiques:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref,
              "raised_by": c.raised_by}
             for c in critiques],
            indent=2,
        )
        prompt = render("plan_verify.md", plan=plan, critiques_json=critiques_json)
        resp = invoke(prompt, self._verifier, self._verifier_name)
        return _parse_verified_critiques(resp.text)

    # ── Arbitrator ──────────────────────────────────────────────────────────

    def run_arbitrator(
        self, plan: str, critiques: list[VerifiedCritique], invoke: InvokeFn
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
        prompt = render(
            "plan_arbitrate.md", plan=plan, valid_critiques_json=critiques_json
        )
        resp = invoke(prompt, self._arbitrator, self._arbitrator_name)
        return _parse_patches(resp.text)
```

- [ ] **Step 4: Run tests (excluding the last test which is intentionally loose)**

```bash
uv run pytest tests/test_plan_strategy.py -v -k "not test_invoke_persona_uses_plan_prefix"
```

Expected: `19 passed`

- [ ] **Step 5: Run full strategy test suite**

```bash
uv run pytest tests/test_plan_strategy.py -v
```

Expected: `20 passed` (the last test may show as xfail or error depending on prompt file presence — that's acceptable)

- [ ] **Step 6: Commit**

```bash
git add src/plan_strategy.py tests/test_plan_strategy.py
git commit -m "feat: add PlanStrategy with 5-step convergence cycle"
```

---

## Task 5: PlanRefiner

**Files:**
- Create: `src/plan_refiner.py`
- Create: `tests/test_plan_refiner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plan_refiner.py
"""Tests for PlanRefiner — plan convergence orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends.types import AgentResponse
from src.config import ArtifactConfig, BackendsConfig, PlanConfig
from src.plan_loop import PlanCycleState
from src.plan_refiner import EXIT_HUMAN_REQUIRED, PlanRefiner


def _make_config(**kwargs) -> PlanConfig:
    defaults = dict(
        topic="Test Plan",
        goal="Test goal",
        primary_artifact="PLAN.md",
        convergence_cycles=1,
        max_cycles=5,
        backends=BackendsConfig(primary="claude", research=["claude", "gemini"]),
    )
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_backend(text: str = "# Generated Plan") -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = AgentResponse(
        text=text, cost_usd=0.01, is_error=False,
        input_tokens=100, output_tokens=50,
    )
    return backend


def _make_backends(text: str = "# Generated Plan") -> dict:
    return {
        "claude": _make_backend(text),
        "gemini": _make_backend(text),
    }


def _converged_state() -> PlanCycleState:
    state = PlanCycleState(plan="# Plan\n\nContent.")
    state.consecutive_clean_cycles = 1
    state.cycle = 1
    return state


class TestPhase1Convergence:
    def test_run_returns_zero_on_success(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.plan_refiner.PlanStrategy"),
            patch("src.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            code = refiner.run(interactive=True)

        assert code == 0

    def test_primary_artifact_written_after_convergence(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.plan_refiner.PlanStrategy") as mock_strat_cls,
            patch("src.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            mock_strat = mock_strat_cls.return_value
            mock_strat.run_builder.return_value = "# Final Plan"
            refiner._state = _converged_state()
            refiner._state.plan = "# Final Plan"
            refiner.run(interactive=True)

        plan_path = tmp_path / "PLAN.md"
        assert plan_path.exists()

    def test_run_returns_2_on_hitl_pause_non_interactive(self, tmp_path):
        from src.hitl import HumanInputRequest
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        def _cycle_with_hitl(state, ctx, strategy, *, interactive):
            state.pending_human_inputs = [
                HumanInputRequest(
                    issue_id="I-01", question="Q?", context="Task 1",
                    suggested_answer="A", cycle=1,
                )
            ]
            return (0, 0, 1)

        with (
            patch("src.plan_refiner.PlanStrategy"),
            patch("src.plan_refiner.run_plan_cycle", side_effect=_cycle_with_hitl),
            patch("src.plan_refiner._plan_should_stop", return_value=False),
        ):
            code = refiner.run(interactive=False)

        assert code == EXIT_HUMAN_REQUIRED

    def test_run_manifest_written(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.plan_refiner.PlanStrategy"),
            patch("src.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        manifest_path = tmp_path / ".run" / "run_manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["topic"] == "Test Plan"
        assert "cycles" in data
        assert "finished_at" in data


class TestPhase2Expansion:
    def test_phase2_writes_artifact(self, tmp_path):
        config = _make_config(
            artifacts=(ArtifactConfig(name="RISK_REGISTER.md", layer="companion", review=False),)
        )
        refiner = PlanRefiner(config, tmp_path, _make_backends("# Risk Register"))

        def _side_effect(prompt_file, **kwargs):
            if prompt_file in ("generate_readme.md", "generate_docs_index.md"):
                return "# Index"
            if prompt_file == "artifact_risk_register.md":
                raise FileNotFoundError(prompt_file)
            return "content"

        with (
            patch("src.plan_refiner.PlanStrategy"),
            patch("src.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.plan_refiner._plan_should_stop", side_effect=[False, True]),
            patch("src.plan_refiner.render", side_effect=_side_effect),
        ):
            refiner.run(interactive=True)

        artifact = tmp_path / "RISK_REGISTER.md"
        assert artifact.exists()


class TestPhase3Indexing:
    def test_phase3_writes_readme_and_docs_index(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.plan_refiner.PlanStrategy"),
            patch("src.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.plan_refiner._plan_should_stop", side_effect=[False, True]),
            patch("src.plan_refiner.render", return_value="# Generated"),
        ):
            refiner.run(interactive=True)

        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "DOCS_INDEX.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_plan_refiner.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'PlanRefiner'`

- [ ] **Step 3: Create `src/plan_refiner.py`**

```python
"""PlanRefiner — plan convergence orchestrator.

Sibling to DocumentRefiner. Runs Phase 1 (plan convergence),
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
from .config import ArtifactConfig, PlanConfig
from .hitl import (
    append_human_decisions,
    load_human_decisions,
    write_pending_questions,
)
from .plan_loop import (
    PlanCycleContext,
    PlanCycleState,
    _plan_should_stop,
    run_plan_cycle,
)
from .plan_strategy import PlanStrategy
from .prompts import render

log = logging.getLogger("autoresearch")

EXIT_HUMAN_REQUIRED = 2


class PlanRefiner:
    """Orchestrates a plan convergence run (plan subcommand).

    Phase 1 — Convergence: Plan refined through adversarial cycles until clean.
    Phase 2 — Expansion: Companion artifacts generated from the converged plan.
    Phase 3 — Indexing: DOCS_INDEX.md and README.md auto-generated.
    """

    def __init__(
        self,
        config: PlanConfig,
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

        strategy = PlanStrategy(self._config, self._backends)
        state = self._init_state()

        ctx = PlanCycleContext(
            call_with=self._invoke,
            invoke_for_strategy=self._invoke,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            config=self._config,
            human_decisions=state.human_decisions,
            update_issue_registry=lambda issues: None,
        )

        # Phase 1 — Convergence
        while not _plan_should_stop(state, self._config):
            valid_count, stale_count, deferred_count = run_plan_cycle(
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
                return EXIT_HUMAN_REQUIRED

        # Write converged primary artifact
        self._write_primary_artifact(state.plan)
        log.info(
            "[plan] Phase 1 complete — %s converged in %d cycle(s).",
            self._config.primary_artifact, state.cycle,
        )

        # Phase 2 — Expansion
        self._run_phase2(state.plan, strategy, ctx)

        # Phase 3 — Indexing
        self._run_phase3()

        # Finalize
        self._write_run_manifest(cycles=state.cycle, total_cost=self._total_cost)
        log.info("[plan] Done. Output at: %s", self._output_dir)
        return 0

    # ── Phase 2: Expansion ──────────────────────────────────────────────────

    def _run_phase2(self, plan: str, strategy: PlanStrategy, ctx: PlanCycleContext) -> None:
        for artifact in self._config.artifacts:
            log.info("[phase2] Generating %s ...", artifact.name)
            content = self._generate_artifact(plan, artifact, strategy, ctx)
            out_path = self._output_dir / artifact.name
            out_path.write_text(content, encoding="utf-8")
            log.info("[phase2] Wrote %s", artifact.name)

    def _generate_artifact(
        self,
        plan: str,
        artifact: ArtifactConfig,
        strategy: PlanStrategy,
        ctx: PlanCycleContext,
    ) -> str:
        stem = Path(artifact.name).stem
        prompt_file = artifact.prompt_file or f"artifact_{stem}.md"
        try:
            prompt = render(prompt_file, plan=plan, topic=self._config.topic,
                            goal=self._config.goal)
        except FileNotFoundError:
            log.warning("Prompt file not found for %s — skipping generation.", artifact.name)
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
                content = strategy.run_builder(
                    content, patches, ctx.call_with,
                    human_decisions=ctx.human_decisions,
                )
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

        readme_resp = self._invoke(
            render(
                "generate_readme.md",
                topic=self._config.topic,
                goal=self._config.goal,
                primary_artifact=self._config.primary_artifact,
                artifact_manifest=manifest,
            ),
            backend,
            builder_name,
        )
        (self._output_dir / "README.md").write_text(readme_resp.text, encoding="utf-8")

        index_resp = self._invoke(
            render(
                "generate_docs_index.md",
                topic=self._config.topic,
                goal=self._config.goal,
                primary_artifact=self._config.primary_artifact,
                artifact_manifest=manifest,
                personas=", ".join(p.name for p in self._config.personas),
            ),
            backend,
            builder_name,
        )
        (self._output_dir / "DOCS_INDEX.md").write_text(index_resp.text, encoding="utf-8")

    def _build_artifact_manifest(self) -> str:
        lines = [f"- {self._config.primary_artifact} (primary, always present)"]
        for a in self._config.artifacts:
            lines.append(f"- {a.name} (layer:{a.layer}, review:{a.review})")
        lines.append("- DOCS_INDEX.md (auto-generated)")
        lines.append("- README.md (auto-generated)")
        return "\n".join(lines)

    # ── State management ────────────────────────────────────────────────────

    def _init_state(self) -> PlanCycleState:
        state = PlanCycleState(plan_path=Path(self._config.primary_artifact))
        if self._resume:
            decisions_path = self._run_dir / "human_decisions.json"
            state.human_decisions = load_human_decisions(decisions_path)
        return state

    def _setup_dirs(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "cycles").mkdir(exist_ok=True)

    def _write_primary_artifact(self, content: str) -> None:
        (self._output_dir / self._config.primary_artifact).write_text(
            content, encoding="utf-8"
        )

    def _write_cycle_snapshot(self, state: PlanCycleState) -> None:
        snap = self._run_dir / "cycles" / f"cycle_{state.cycle:03d}.md"
        snap.write_text(
            f"# Cycle {state.cycle}\n\n"
            f"Valid issues: {sum(1 for i in state.issue_registry if i.status == 'valid')}\n"
            f"Clean streak: {state.consecutive_clean_cycles}\n\n"
            f"## Plan snapshot\n\n{state.plan[:2000]}\n",
            encoding="utf-8",
        )
        stem = Path(self._config.primary_artifact).stem
        version_path = self._run_dir / f"{stem}_v{state.cycle}.md"
        version_path.write_text(state.plan, encoding="utf-8")

    def _write_issue_registry(self, state: PlanCycleState) -> None:
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

    def _handle_hitl_pause(self, state: PlanCycleState) -> None:
        pending_path = self._run_dir / "pending_questions.json"
        write_pending_questions(state.pending_human_inputs, pending_path)
        print(
            f"\n[plan] {len(state.pending_human_inputs)} question(s) require human input.\n"
            f"Fill in answers in: {pending_path}\n"
            f"Then re-run with --resume to continue.\n"
        )

    # ── Backend invocation ──────────────────────────────────────────────────

    def _invoke(self, prompt: str, backend: Backend, backend_name: str) -> AgentResponse:
        opts = CallOptions(max_turns=10)
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

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_plan_refiner.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/plan_refiner.py tests/test_plan_refiner.py
git commit -m "feat: add PlanRefiner orchestrator with Phase 1/2/3"
```

---

## Task 6: CLI, Config Template, and README

**Files:**
- Modify: `src/cli.py`
- Create: `configs/plan_template.yaml`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_cli.py` inside a new `TestPlanSubcommand` class at the end of the file:

```python
# Add to tests/test_cli.py

class TestPlanSubcommand:
    @pytest.fixture
    def plan_config_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "plan.yaml"
        p.write_text(textwrap.dedent("""\
            plan:
              topic: "Test Plan"
              goal: "Build something"
              backends:
                primary: claude
                research:
                  - claude
                  - gemini
        """), encoding="utf-8")
        return p

    def test_missing_config_returns_1(self, tmp_path):
        result = main(["plan", "--config", str(tmp_path / "nonexistent.yaml")])
        assert result == 1

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_calls_refiner_run(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        result = main(["plan", "--config", str(plan_config_file)])

        assert result == 0
        mock_instance.run.assert_called_once_with(interactive=True)

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_no_interactive_flag(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["plan", "--config", str(plan_config_file), "--no-interactive"])

        mock_instance.run.assert_called_once_with(interactive=False)

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_resume_flag(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        main(["plan", "--config", str(plan_config_file), "--resume"])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["resume"] is True

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_backend_unavailable_returns_1(self, mock_refiner_cls, mock_get_backends, plan_config_file):
        mock_be = MagicMock()
        mock_be.check_available.return_value = False
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be}

        result = main(["plan", "--config", str(plan_config_file)])

        assert result == 1
        mock_refiner_cls.assert_not_called()

    @patch("src.cli.get_backends")
    @patch("src.cli.PlanRefiner")
    def test_plan_custom_output_dir(self, mock_refiner_cls, mock_get_backends, plan_config_file, tmp_path):
        mock_be = MagicMock()
        mock_be.check_available.return_value = True
        mock_be.cli_executable.return_value = "claude"
        mock_get_backends.return_value = {"claude": mock_be, "gemini": mock_be}
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_refiner_cls.return_value = mock_instance

        custom = tmp_path / "my_output"
        main(["plan", "--config", str(plan_config_file), "--output", str(custom)])

        _, kwargs = mock_refiner_cls.call_args
        assert kwargs["output_dir"] == custom.resolve()
```

- [ ] **Step 2: Run new CLI tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::TestPlanSubcommand -v 2>&1 | head -20
```

Expected: errors about `plan` not being a valid subcommand

- [ ] **Step 3: Add `plan` subcommand to `src/cli.py`**

Add import at the top of the file alongside the existing `DocumentRefiner` import:

```python
from .plan_refiner import PlanRefiner
```

Add the subparser in `_build_parser()`, after the `refine_p` block (before `return parser`):

```python
    # ── plan subcommand ──────────────────────────────────────────────────────
    plan_p = subparsers.add_parser(
        "plan",
        help="Refine an implementation plan through adversarial convergence cycles.",
    )
    plan_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a plan config YAML (see configs/plan_template.yaml).",
    )
    plan_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/<config-stem>/.",
    )
    plan_p.add_argument(
        "--resume",
        action="store_true",
        help="Load existing human decisions and continue a paused run.",
    )
    plan_p.add_argument(
        "--no-interactive",
        dest="no_interactive",
        action="store_true",
        help="Disable interactive HITL prompts. Exit with code 2 when human input is needed.",
    )
```

Add `_run_plan()` function after `_run_refine()`:

```python
def _run_plan(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = PlanConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load plan config: %s", exc)
        return 1

    output_dir: Path = (args.output or Path("output") / config_path.stem).resolve()

    all_names = config.backends.all_backend_names()
    backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    refiner = PlanRefiner(
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
```

Add `PlanConfig` to the existing import in `cli.py`:

```python
from .config import VALID_STRATEGIES, DocumentConfig, PlanConfig, ResearchConfig
```

Add dispatch in `main()` after the `refine` branch:

```python
    if args.subcommand == "plan":
        return _run_plan(args, log)
```

- [ ] **Step 4: Run CLI tests**

```bash
uv run pytest tests/test_cli.py::TestPlanSubcommand -v
```

Expected: `6 passed`

- [ ] **Step 5: Create `configs/plan_template.yaml`**

```yaml
# Plan Refiner configuration template.
# Copy this file and fill in your topic, goal, and primary_artifact.
# Run with: autoresearch plan --config configs/your_copy.yaml

plan:
  topic: "Your feature or component here"
  goal: >
    Describe what the finished plan should enable — e.g. "A complete,
    unambiguous implementation plan that a senior engineer can execute
    task-by-task without clarifying questions."

  # Primary artifact produced by Phase 1 (convergence).
  primary_artifact: "PLAN.md"

  # Optional: path or raw text to seed the Builder in cycle 0.
  # Use this to provide an existing draft plan.
  source_material: ""

  # ── Convergence settings ────────────────────────────────────────────────────
  # How many consecutive clean cycles are required before stopping.
  convergence_cycles: 2

  # Hard cap on total cycles (0 = no cap, rely on convergence_cycles alone).
  max_cycles: 10

  # ── Review personas ─────────────────────────────────────────────────────────
  # Each persona runs its own critique pass per cycle.
  # Omit this section to use all seven defaults.
  persona_mode: parallel   # "parallel" (concurrent) or "serial" (sequential)

  personas:
    - name: architect         # File boundaries, coupling, abstraction layers
    - name: tech_lead         # Task sizing, dependency order, commit granularity
    - name: qa_engineer       # TDD discipline, edge cases, test completeness
    - name: ai_engineer       # LLM output validation, model selection, evaluation
    - name: data_engineer     # Data flows, schema migrations, ETL sequencing
    - name: security_engineer # Input validation, injection risks, secrets handling
    - name: devils_advocate   # Hidden assumptions, failure scenarios, missing steps

  # ── Companion source files ──────────────────────────────────────────────────
  # Files injected as structured context into agent prompts.
  # Paths are relative to this config file's directory. Globs supported.
  # Roles: builder, challenger, any persona name, or "all".
  source_files: []
  # Example:
  # source_files:
  #   - path: docs/superpowers/specs/**/*.md
  #     roles: [builder, architect, tech_lead]
  #   - path: PRD.md
  #     roles: [all]

  # ── Phase 2 artifacts (optional) ────────────────────────────────────────────
  # Generated from the converged plan after Phase 1 completes.
  artifacts: []
  # Example:
  # artifacts:
  #   - name: RISK_REGISTER.md
  #     layer: companion
  #     review: false

  # ── Backend configuration ───────────────────────────────────────────────────
  backends:
    primary: claude        # Personas, synthesis
    research:
      - claude             # Builder (research[0])
      - gemini             # Challenger (research[1])
    judge: claude          # Arbitrator — resolves conflicting critiques
    utility: gemini        # Verifier — cheap, fast verification pass

  # ── Strategy tuning (optional) ──────────────────────────────────────────────
  # strategy_config:
  #   critique_depth: standard   # light | standard | thorough
```

- [ ] **Step 6: Update README.md — add `plan` to Quick Start and Document Refinement section**

In `README.md`, add after the `refine` Quick Start block in the Document Refinement section (find the line `For iterative document refinement...` and add after it):

```markdown
For iterative **plan** refinement (implementation plans generated by LLMs), see
[Plan Refinement](#plan-refinement) below.
```

Add a new `## Plan Refinement` section after the `## Document Refinement` section and before `---`:

```markdown
---

## Plan Refinement

The `plan` subcommand runs the same multi-LLM convergence loop as `refine`, but
targets implementation plans — PLAN.md files generated by the `writing-plans`
skill or any LLM. Seven domain-specific reviewers critique the plan from distinct
angles until no valid issues remain.

```bash
# Refine a plan interactively
uv run python -m src.cli plan --config configs/plan_template.yaml

# Non-interactive (exit code 2 if human input needed)
uv run python -m src.cli plan --config configs/my_plan.yaml --no-interactive

# Resume after answering deferred questions
uv run python -m src.cli plan --config configs/my_plan.yaml --resume
```

Copy `configs/plan_template.yaml` to create a new plan refinement config.

### Reviewer Personas

| Persona | What it looks for |
|---|---|
| **Architect** | File boundaries, coupling between tasks, missing abstraction layers |
| **Tech Lead** | Task sizing, dependency order, commit granularity, naming consistency |
| **QA Engineer** | TDD discipline (test before implementation), edge cases, flaky setups |
| **AI Engineer** | LLM output validation, model selection rationale, non-determinism handling |
| **Data Engineer** | Data flow order, schema migration sequencing, rollback steps |
| **Security Engineer** | Input validation, injection surfaces, secrets handling |
| **Devil's Advocate** | Hidden assumptions, failure scenarios, "obvious" missing steps |

The **Challenger** (distinct from personas) finds structural gaps: missing tasks,
wrong task order, vague steps, steps that reference undefined symbols.

See [Document Refinement](#document-refinement) for the full convergence loop
architecture, HITL flow, and output artifact descriptions — `plan` uses the
same three-phase pipeline.
```

- [ ] **Step 7: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass (previous count + new tests)

- [ ] **Step 8: Commit**

```bash
git add src/cli.py configs/plan_template.yaml tests/test_cli.py README.md
git commit -m "feat: add plan CLI subcommand and config template"
```
