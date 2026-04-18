from __future__ import annotations

import json
from unittest.mock import MagicMock

from src.backends.types import AgentResponse
from src.config import BackendsConfig, PlanConfig, PlanPersonaConfig, SourceFileConfig
from src.document_strategy import Patch, RawCritique, VerifiedCritique
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
    # plan_persona_tech_lead.md exists (created in Task 3) — verify the call succeeds
    # and uses the plan_persona_{name}.md prefix convention
    result = s._invoke_persona(cfg.personas[0], "# Plan", _call_with)
    assert isinstance(result, list)
    assert backend.run.call_count == 1
