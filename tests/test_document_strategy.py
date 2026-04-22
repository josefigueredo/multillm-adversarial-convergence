from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends.types import AgentResponse
from src.config import BackendsConfig, DocumentConfig, PersonaConfig, SourceFileConfig
from src.document_strategy import (
    ConvergeStrategy,
    Patch,
    RawCritique,
    VerifiedCritique,
    _extract_json,
    _format_human_decisions,
    _format_patches,
    _parse_patches,
    _parse_raw_critiques,
    _parse_verified_critiques,
)
from src.hitl import DeferReason, HumanDecision


def _make_backend(text: str = "{}") -> MagicMock:
    b = MagicMock()
    b.run.return_value = AgentResponse(
        text=text, cost_usd=0.01, is_error=False, input_tokens=10, output_tokens=20
    )
    return b


def _make_config(**kwargs) -> DocumentConfig:
    defaults = {"topic": "T", "goal": "G"}
    defaults.update(kwargs)
    return DocumentConfig(**defaults)


def _make_strategy(backends_dict=None, **cfg_kwargs) -> ConvergeStrategy:
    cfg = _make_config(**cfg_kwargs)
    if backends_dict is None:
        backends_dict = {"claude-cli": _make_backend()}
    return ConvergeStrategy(cfg, backends_dict)


def _call_with(prompt, backend_obj, backend_name):
    return backend_obj.run(prompt, None)


# ── Backend role resolution ──────────────────────────────────────────────────

def test_builder_uses_research_0():
    codex = _make_backend()
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude-cli", research=("codex-cli", "claude-cli")),
    )
    s = ConvergeStrategy(cfg, {"codex-cli": codex, "claude-cli": claude})
    assert s._builder is codex
    assert s._builder_name == "codex-cli"


def test_challenger_uses_research_1():
    codex = _make_backend()
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude-cli", research=("codex-cli", "claude-cli")),
    )
    s = ConvergeStrategy(cfg, {"codex-cli": codex, "claude-cli": claude})
    assert s._challenger is claude
    assert s._challenger_name == "claude-cli"


def test_challenger_falls_back_to_primary_when_only_one_research():
    claude = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude-cli", research=("claude-cli",)),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": claude})
    assert s._challenger is claude


def test_verifier_uses_utility():
    claude = _make_backend()
    utility = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude-cli", utility="utility_be"),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": claude, "utility_be": utility})
    assert s._verifier is utility


def test_arbitrator_uses_judge():
    claude = _make_backend()
    gemini = _make_backend()
    cfg = DocumentConfig(
        topic="T", goal="G",
        backends=BackendsConfig(primary="claude-cli", judge="gemini-cli"),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": claude, "gemini-cli": gemini})
    assert s._arbitrator is gemini


# ── run_builder ──────────────────────────────────────────────────────────────

def test_run_builder_returns_text():
    backend = _make_backend("Generated PRD content")
    s = _make_strategy({"claude-cli": backend})
    result = s.run_builder("", [], _call_with, human_decisions=[])
    assert result == "Generated PRD content"


def test_run_builder_includes_human_decisions_in_prompt():
    backend = _make_backend("Updated PRD")
    s = _make_strategy({"claude-cli": backend})
    prompts_seen = []

    def capturing_call(prompt, b, name):
        prompts_seen.append(prompt)
        return b.run(prompt, None)

    decision = HumanDecision(
        issue_id="I-01", question="Q?", answer="A!",
        answered_at="2026-01-01T00:00:00+00:00", answered_by="human",
    )
    s.run_builder("existing prd", [], capturing_call, human_decisions=[decision])
    assert "I-01" in prompts_seen[0]
    assert "A!" in prompts_seen[0]


# ── run_challenger ────────────────────────────────────────────────────────────

def test_run_challenger_parses_json_array():
    response_json = json.dumps([
        {"description": "§3 contradicts §7", "section_ref": "§3", "raised_by": "challenger"}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude-cli": backend})
    critiques = s.run_challenger("prd text", _call_with)
    assert len(critiques) == 1
    assert isinstance(critiques[0], RawCritique)
    assert critiques[0].section_ref == "§3"
    assert critiques[0].raised_by == "challenger"


def test_run_challenger_handles_empty_array():
    backend = _make_backend("[]")
    s = _make_strategy({"claude-cli": backend})
    critiques = s.run_challenger("prd", _call_with)
    assert critiques == []


def test_run_challenger_handles_malformed_json():
    backend = _make_backend("not json at all")
    s = _make_strategy({"claude-cli": backend})
    critiques = s.run_challenger("prd", _call_with)
    assert critiques == []


# ── run_verifier ──────────────────────────────────────────────────────────────

def test_run_verifier_classifies_valid():
    raw = [RawCritique(description="d", section_ref="§1", raised_by="challenger")]
    response_json = json.dumps([
        {"description": "d", "section_ref": "§1", "raised_by": "challenger",
         "status": "valid", "defer_reason": None, "question": None, "suggested_answer": None}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude-cli": backend})
    verified = s.run_verifier("prd", raw, _call_with)
    assert len(verified) == 1
    assert verified[0].status == "valid"
    assert verified[0].defer_reason is None


def test_run_verifier_classifies_human_required():
    raw = [RawCritique(description="ambiguous", section_ref="§5", raised_by="architect")]
    response_json = json.dumps([
        {
            "description": "ambiguous", "section_ref": "§5", "raised_by": "architect",
            "status": "deferred", "defer_reason": "human_required",
            "question": "Which topology?", "suggested_answer": "One per tenant",
        }
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude-cli": backend})
    verified = s.run_verifier("prd", raw, _call_with)
    assert verified[0].defer_reason == DeferReason.HUMAN_REQUIRED
    assert verified[0].question == "Which topology?"
    assert verified[0].suggested_answer == "One per tenant"


def test_run_verifier_returns_empty_for_no_critiques():
    s = _make_strategy()
    result = s.run_verifier("prd", [], _call_with)
    assert result == []


# ── run_arbitrator ────────────────────────────────────────────────────────────

def test_run_arbitrator_returns_patches():
    critiques = [
        VerifiedCritique(description="d", section_ref="§3", raised_by="challenger", status="valid")
    ]
    response_json = json.dumps([
        {"section_ref": "§3", "proposed_text": "New text", "rationale": "Because X"}
    ])
    backend = _make_backend(response_json)
    s = _make_strategy({"claude-cli": backend})
    patches = s.run_arbitrator("prd", critiques, _call_with)
    assert len(patches) == 1
    assert isinstance(patches[0], Patch)
    assert patches[0].proposed_text == "New text"


def test_run_arbitrator_returns_empty_for_no_valid():
    s = _make_strategy()
    patches = s.run_arbitrator("prd", [], _call_with)
    assert patches == []


def test_run_arbitrator_skips_non_valid_critiques():
    critiques = [
        VerifiedCritique(description="s", section_ref="§1", raised_by="challenger", status="stale"),
        VerifiedCritique(description="d", section_ref="§2", raised_by="architect",
                         status="deferred", defer_reason="human_required"),
    ]
    s = _make_strategy()
    # Should not call the backend at all since no valid critiques
    patches = s.run_arbitrator("prd", critiques, _call_with)
    assert patches == []


# ── run_personas ──────────────────────────────────────────────────────────────

def test_run_personas_parallel_returns_merged():
    backend = _make_backend(json.dumps([
        {"description": "persona critique", "section_ref": "§2", "raised_by": "architect"}
    ]))
    cfg = DocumentConfig(topic="T", goal="G", persona_mode="parallel")
    s = ConvergeStrategy(cfg, {"claude-cli": backend})
    critiques = s.run_personas("prd", _call_with)
    # 3 default personas × 1 critique each = 3 total
    assert len(critiques) == 3
    assert all(isinstance(c, RawCritique) for c in critiques)


def test_run_personas_serial_returns_merged():
    backend = _make_backend(json.dumps([
        {"description": "critique", "section_ref": "§1", "raised_by": "scrum_master"}
    ]))
    cfg = DocumentConfig(topic="T", goal="G", persona_mode="serial")
    s = ConvergeStrategy(cfg, {"claude-cli": backend})
    critiques = s.run_personas("prd", _call_with)
    assert len(critiques) == 3


# ── Parsing helpers ───────────────────────────────────────────────────────────

def test_extract_json_from_fenced_block():
    text = '```json\n[{"a": 1}]\n```'
    result = _extract_json(text)
    assert result == [{"a": 1}]


def test_extract_json_from_plain_array():
    text = '[{"a": 1}]'
    result = _extract_json(text)
    assert result == [{"a": 1}]


def test_format_human_decisions_empty():
    assert _format_human_decisions([]) == ""


def test_format_human_decisions_with_entries():
    d = HumanDecision(issue_id="I-01", question="Q?", answer="A!",
                      answered_at="2026-01-01T00:00:00+00:00", answered_by="human")
    result = _format_human_decisions([d])
    assert "I-01" in result
    assert "A!" in result


def test_format_patches_empty():
    result = _format_patches([])
    assert "no patches" in result


def test_format_patches_with_entries():
    p = Patch(section_ref="§3", proposed_text="new text", rationale="because")
    result = _format_patches([p])
    assert "§3" in result
    assert "new text" in result


# ── _source_block ────────────────────────────────────────────────────────────

def test_source_block_empty_when_no_source_files():
    s = _make_strategy()
    assert s._source_block("builder") == ""
    assert "## Reference Files" not in s._source_block("builder")


def test_source_block_returns_content_for_matching_role(tmp_path):
    f = tmp_path / "arch.md"
    f.write_text("# Architecture\n\nContent here.")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend()})
    block = s._source_block("builder")
    assert "arch.md" in block
    assert "# Architecture" in block
    assert "## Reference Files" in block


def test_source_block_excludes_files_not_matching_role(tmp_path):
    f = tmp_path / "file.md"
    f.write_text("secret content")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend()})
    assert s._source_block("builder") == ""
    assert "secret content" in s._source_block("architect")


def test_source_block_warns_and_skips_unreadable_file(tmp_path, caplog):
    f = tmp_path / "gone.md"
    f.write_text("content")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend()})
    f.unlink()
    with caplog.at_level(logging.WARNING):
        block = s._source_block("builder")
    assert block == ""
    assert "gone.md" in caplog.text


def test_run_builder_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Reference Doc")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend("# PRD Output")})
    with patch("src.document_strategy.render", return_value="prompt") as mock_render:
        s.run_builder("", [], _call_with, human_decisions=[])
    _, kwargs = mock_render.call_args
    assert "# Reference Doc" in kwargs["source_files"]


def test_run_challenger_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Challenger Ref")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("challenger",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend("[]")})
    with patch("src.document_strategy.render", return_value="[]") as mock_render:
        s.run_challenger("prd text", _call_with)
    _, kwargs = mock_render.call_args
    assert "# Challenger Ref" in kwargs["source_files"]


def test_invoke_persona_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Architect Ref")
    cfg = DocumentConfig(
        topic="T", goal="G",
        personas=(PersonaConfig("architect"),),
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend("[]")})
    with patch("src.document_strategy.render", return_value="[]") as mock_render:
        s._invoke_persona(cfg.personas[0], "prd", _call_with)
    _, kwargs = mock_render.call_args
    assert "# Architect Ref" in kwargs["source_files"]


def test_run_builder_source_files_empty_when_no_match(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Persona Only")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude-cli": _make_backend("# PRD")})
    with patch("src.document_strategy.render", return_value="prompt") as mock_render:
        s.run_builder("", [], _call_with, human_decisions=[])
    _, kwargs = mock_render.call_args
    assert kwargs["source_files"] == ""
