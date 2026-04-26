"""Integration tests for MM08 Step 3: guidance persistence and injection wiring.

These tests verify that:
1. Guidance saved at a pause is available after resume (store round-trip).
2. Only matching (workflow, target, trigger) guidance is injected.
3. The next phase builder prompt contains the formatted guidance block.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.backends.types import AgentResponse
from src.config import DocumentConfig, PlanConfig
from src.document_strategy import ConvergeStrategy
from src.plan_strategy import PlanStrategy
from src.workflows.gates import GateTrigger, GateTarget
from src.workflows.guidance import (
    GuidanceStore,
    HitlGuidance,
    format_guidance_block,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guidance(
    workflow: str = "refine",
    target: str = "verifier",
    trigger: str = "after",
    text: str = "Please focus on clarity.",
    sequence: int = 1,
) -> HitlGuidance:
    return HitlGuidance(
        workflow=workflow,
        target=target,
        target_type=GateTarget.PHASE,
        gate_trigger=GateTrigger(trigger),
        guidance_text=text,
        guidance_type="steer",
        sequence=sequence,
    )


def _make_backend(text: str = "result") -> MagicMock:
    b = MagicMock()
    b.run.return_value = AgentResponse(
        text=text, cost_usd=0.0, is_error=False, input_tokens=1, output_tokens=1
    )
    return b


# ---------------------------------------------------------------------------
# 1. Store round-trip: guidance saved at pause is available on resume
# ---------------------------------------------------------------------------

def test_guidance_available_after_pause(tmp_path):
    store = GuidanceStore(tmp_path)
    g = _make_guidance(text="Approve scope changes in section 3.")
    store.save(g)

    loaded = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert len(loaded) == 1
    assert loaded[0].guidance_text == "Approve scope changes in section 3."


def test_multiple_guidance_records_all_available(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(text="First note."))
    store.save(_make_guidance(text="Second note."))

    loaded = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert len(loaded) == 2
    assert loaded[0].guidance_text == "First note."
    assert loaded[1].guidance_text == "Second note."


# ---------------------------------------------------------------------------
# 2. Only matching guidance is injected (workflow/target/trigger filtering)
# ---------------------------------------------------------------------------

def test_only_matching_workflow_guidance_injected(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(workflow="refine", text="Refine guidance."))
    store.save(_make_guidance(workflow="plan", text="Plan guidance."))

    refine_records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert len(refine_records) == 1
    assert refine_records[0].guidance_text == "Refine guidance."

    plan_records = store.load_for_target("plan", "verifier", GateTrigger.AFTER)
    assert len(plan_records) == 1
    assert plan_records[0].guidance_text == "Plan guidance."


def test_only_matching_target_guidance_injected(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(target="verifier", text="Verifier guidance."))
    store.save(_make_guidance(target="builder", text="Builder guidance."))

    verifier_records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert len(verifier_records) == 1
    assert verifier_records[0].guidance_text == "Verifier guidance."


def test_only_matching_trigger_guidance_injected(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(trigger="after", text="After guidance."))
    store.save(_make_guidance(trigger="before", text="Before guidance."))

    after_records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert len(after_records) == 1
    assert after_records[0].guidance_text == "After guidance."


def test_no_records_for_unrelated_workflow(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(workflow="plan", text="Plan only."))

    refine_records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    assert refine_records == []


# ---------------------------------------------------------------------------
# 3. Builder prompt contains formatted guidance block
# ---------------------------------------------------------------------------

def test_document_builder_prompt_contains_guidance_block(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(workflow="refine", text="Emphasise user stories."))
    records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    guidance_context = format_guidance_block(records)

    backend = _make_backend("Updated PRD")
    cfg = DocumentConfig(topic="T", goal="G")
    strategy = ConvergeStrategy(cfg, {"claude-cli": backend})
    captured: list[str] = []

    def capture(prompt, b, name):
        captured.append(prompt)
        return b.run(prompt, None)

    strategy.run_builder("", [], capture, human_decisions=[], guidance_context=guidance_context)
    assert "Emphasise user stories." in captured[0]
    assert "## Human Guidance" in captured[0]


def test_plan_builder_prompt_contains_guidance_block(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(workflow="plan", text="Cover deployment steps."))
    records = store.load_for_target("plan", "verifier", GateTrigger.AFTER)
    guidance_context = format_guidance_block(records)

    backend = _make_backend("Updated Plan")
    cfg = PlanConfig(topic="T", goal="G")
    strategy = PlanStrategy(cfg, {"claude-cli": backend})
    captured: list[str] = []

    def capture(prompt, b, name):
        captured.append(prompt)
        return b.run(prompt, None)

    strategy.run_builder("", [], capture, human_decisions=[], guidance_context=guidance_context)
    assert "Cover deployment steps." in captured[0]
    assert "## Human Guidance" in captured[0]


def test_empty_store_produces_no_guidance_in_prompt(tmp_path):
    store = GuidanceStore(tmp_path)
    records = store.load_for_target("refine", "verifier", GateTrigger.AFTER)
    guidance_context = format_guidance_block(records)

    backend = _make_backend("PRD")
    cfg = DocumentConfig(topic="T", goal="G")
    strategy = ConvergeStrategy(cfg, {"claude-cli": backend})
    captured: list[str] = []

    def capture(prompt, b, name):
        captured.append(prompt)
        return b.run(prompt, None)

    strategy.run_builder("", [], capture, human_decisions=[], guidance_context=guidance_context)
    assert "## Human Guidance" not in captured[0]
