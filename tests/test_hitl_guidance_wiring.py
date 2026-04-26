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


# ---------------------------------------------------------------------------
# 4. Sequence isolation: resume loads only the exact pause sequence
# ---------------------------------------------------------------------------

def test_sequence_2_resume_excludes_sequence_1_guidance(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(text="Old guidance from cycle 1.", sequence=1))
    store.save(_make_guidance(text="New guidance from cycle 2.", sequence=2))

    records_seq2 = store.load_for_target("refine", "verifier", GateTrigger.AFTER, sequence=2)
    assert len(records_seq2) == 1
    assert records_seq2[0].guidance_text == "New guidance from cycle 2."

    records_seq1 = store.load_for_target("refine", "verifier", GateTrigger.AFTER, sequence=1)
    assert len(records_seq1) == 1
    assert records_seq1[0].guidance_text == "Old guidance from cycle 1."


def test_resume_with_no_matching_sequence_gives_empty(tmp_path):
    store = GuidanceStore(tmp_path)
    store.save(_make_guidance(text="Guidance for cycle 1.", sequence=1))

    records = store.load_for_target("refine", "verifier", GateTrigger.AFTER, sequence=3)
    assert records == []
    assert format_guidance_block(records) == ""


# ---------------------------------------------------------------------------
# 5. One-shot consumption: guidance cleared after first builder call
# ---------------------------------------------------------------------------

def test_guidance_cleared_after_first_run_cycle():
    from unittest.mock import MagicMock
    from src.document_loop import CycleContext, CycleState, run_cycle
    from src.audit_trail import NullAuditTrailWriter
    from pathlib import Path

    guidance = "## Human Guidance\n### Steer (verifier, after)\nFocus on clarity."
    ctx = CycleContext(
        call_with=lambda *a, **kw: None,
        invoke_for_strategy=lambda *a, **kw: None,
        track_usage=lambda *a, **kw: None,
        track_cost=lambda *a, **kw: None,
        config=DocumentConfig(topic="T", goal="G"),
        human_decisions=[],
        read_prd_section=lambda s: "",
        update_issue_registry=lambda issues: None,
        audit_trail=NullAuditTrailWriter(),
        artifact_root=Path("."),
        guidance_context=guidance,
    )
    state = CycleState()
    strategy = MagicMock()
    strategy.run_builder.return_value = "PRD"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_cycle(state, ctx, strategy, interactive=False)

    assert ctx.guidance_context == ""
    first_kwargs = strategy.run_builder.call_args_list[0][1]
    assert first_kwargs["guidance_context"] == guidance


def test_guidance_not_replayed_in_second_cycle():
    from unittest.mock import MagicMock
    from src.document_loop import CycleContext, CycleState, run_cycle
    from src.audit_trail import NullAuditTrailWriter
    from pathlib import Path

    guidance = "## Human Guidance\n### Steer\nExpand section 2."
    ctx = CycleContext(
        call_with=lambda *a, **kw: None,
        invoke_for_strategy=lambda *a, **kw: None,
        track_usage=lambda *a, **kw: None,
        track_cost=lambda *a, **kw: None,
        config=DocumentConfig(topic="T", goal="G"),
        human_decisions=[],
        read_prd_section=lambda s: "",
        update_issue_registry=lambda issues: None,
        audit_trail=NullAuditTrailWriter(),
        artifact_root=Path("."),
        guidance_context=guidance,
    )
    state = CycleState()
    strategy = MagicMock()
    strategy.run_builder.return_value = "PRD"
    strategy.run_challenger.return_value = []
    strategy.run_personas.return_value = []
    strategy.run_verifier.return_value = []
    strategy.run_arbitrator.return_value = []

    run_cycle(state, ctx, strategy, interactive=False)  # first cycle: uses guidance
    run_cycle(state, ctx, strategy, interactive=False)  # second cycle: should be empty

    assert strategy.run_builder.call_count == 2
    first_kwargs = strategy.run_builder.call_args_list[0][1]
    second_kwargs = strategy.run_builder.call_args_list[1][1]
    assert first_kwargs["guidance_context"] == guidance
    assert second_kwargs["guidance_context"] == ""

