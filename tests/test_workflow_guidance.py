"""Tests for MM08 Step 3 — HITL guidance persistence and injection.

Covers:
- HitlGuidance dataclass: shape, validation, serialization round-trip
- GuidanceStore: JSONL persistence, load helpers, corrupt-line resilience
- format_guidance_block: prompt injection formatting
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.workflows.guidance import (
    GUIDANCE_FILENAME,
    VALID_GUIDANCE_TYPES,
    GuidanceStore,
    HitlGuidance,
    format_guidance_block,
)
from src.workflows.gates import GateTarget, GateTrigger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_guidance(
    *,
    workflow: str = "research",
    target: str = "hypothesis",
    target_type: str = GateTarget.PHASE,
    gate_trigger: str = GateTrigger.BEFORE,
    guidance_type: str = "steer",
    guidance_text: str = "Focus on cost comparisons.",
    sequence: int = 0,
) -> HitlGuidance:
    return HitlGuidance(
        workflow=workflow,
        target=target,
        target_type=target_type,
        gate_trigger=gate_trigger,
        guidance_type=guidance_type,
        guidance_text=guidance_text,
        sequence=sequence,
    )


# ===========================================================================
# HitlGuidance data model
# ===========================================================================


class TestHitlGuidance:
    def test_is_frozen(self):
        g = _make_guidance()
        with pytest.raises((AttributeError, TypeError)):
            g.guidance_text = "changed"  # type: ignore[misc]

    def test_is_hashable(self):
        g = _make_guidance()
        s = frozenset({g})
        assert g in s

    def test_timestamp_auto_generated(self):
        g = _make_guidance()
        assert isinstance(g.timestamp, str)
        assert len(g.timestamp) > 0

    def test_sequence_defaults_to_zero(self):
        g = _make_guidance()
        assert g.sequence == 0

    def test_explicit_sequence(self):
        g = _make_guidance(sequence=3)
        assert g.sequence == 3

    def test_invalid_guidance_type_raises(self):
        with pytest.raises(ValueError, match="guidance_type"):
            _make_guidance(guidance_type="turbo")

    def test_invalid_workflow_raises(self):
        with pytest.raises(ValueError, match="workflow"):
            _make_guidance(workflow="plans")

    def test_invalid_gate_trigger_raises(self):
        with pytest.raises(ValueError, match="gate_trigger"):
            _make_guidance(gate_trigger="sideways")

    def test_invalid_target_type_raises(self):
        with pytest.raises(ValueError, match="target_type"):
            _make_guidance(target_type="subroutine")

    def test_all_valid_guidance_types_accepted(self):
        for gt in VALID_GUIDANCE_TYPES:
            _make_guidance(guidance_type=gt)  # should not raise

    def test_to_dict_contains_required_keys(self):
        g = _make_guidance()
        d = g.to_dict()
        for key in ("workflow", "target", "target_type", "gate_trigger",
                    "guidance_type", "guidance_text", "sequence", "timestamp"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_values(self):
        g = _make_guidance(
            workflow="refine",
            target="verifier",
            target_type=GateTarget.PHASE,
            gate_trigger=GateTrigger.AFTER,
            guidance_type="approve",
            guidance_text="Looks good.",
            sequence=2,
        )
        d = g.to_dict()
        assert d["workflow"] == "refine"
        assert d["target"] == "verifier"
        assert d["target_type"] == "phase"
        assert d["gate_trigger"] == "after"
        assert d["guidance_type"] == "approve"
        assert d["guidance_text"] == "Looks good."
        assert d["sequence"] == 2

    def test_from_dict_round_trip(self):
        g = _make_guidance(guidance_type="reject", guidance_text="Redo this.")
        g2 = HitlGuidance.from_dict(g.to_dict())
        assert g2.workflow == g.workflow
        assert g2.target == g.target
        assert g2.target_type == g.target_type
        assert g2.gate_trigger == g.gate_trigger
        assert g2.guidance_type == g.guidance_type
        assert g2.guidance_text == g.guidance_text
        assert g2.sequence == g.sequence
        assert g2.timestamp == g.timestamp

    def test_from_dict_sequence_defaults_to_zero_if_missing(self):
        d = _make_guidance().to_dict()
        d.pop("sequence")
        g = HitlGuidance.from_dict(d)
        assert g.sequence == 0

    def test_checkpoint_target_type_accepted(self):
        g = _make_guidance(target_type=GateTarget.CHECKPOINT, target="convergence")
        assert g.target_type == "checkpoint"

    def test_plan_workflow_accepted(self):
        g = _make_guidance(workflow="plan")
        assert g.workflow == "plan"


# ===========================================================================
# GuidanceStore
# ===========================================================================


class TestGuidanceStore:
    def test_save_creates_file(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g = _make_guidance()
        store.save(g)
        assert (tmp_path / GUIDANCE_FILENAME).exists()

    def test_save_appends_multiple_records(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g1 = _make_guidance(guidance_text="First")
        g2 = _make_guidance(guidance_text="Second")
        store.save(g1)
        store.save(g2)
        lines = (tmp_path / GUIDANCE_FILENAME).read_text().strip().splitlines()
        assert len(lines) == 2

    def test_load_all_empty_when_no_file(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        assert store.load_all() == []

    def test_load_all_returns_records_in_order(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g1 = _make_guidance(guidance_text="First")
        g2 = _make_guidance(guidance_text="Second")
        store.save(g1)
        store.save(g2)
        records = store.load_all()
        assert len(records) == 2
        assert records[0].guidance_text == "First"
        assert records[1].guidance_text == "Second"

    def test_load_all_skips_corrupt_json_lines(self, tmp_path: Path):
        path = tmp_path / GUIDANCE_FILENAME
        good = _make_guidance(guidance_text="Valid")
        path.write_text("not valid json\n" + json.dumps(good.to_dict()) + "\n")
        store = GuidanceStore(tmp_path)
        records = store.load_all()
        assert len(records) == 1
        assert records[0].guidance_text == "Valid"

    def test_load_all_skips_schema_invalid_records(self, tmp_path: Path):
        path = tmp_path / GUIDANCE_FILENAME
        bad = {"workflow": "research", "target": "hypothesis"}  # missing required keys
        good = _make_guidance(guidance_text="Good")
        path.write_text(
            json.dumps(bad) + "\n" + json.dumps(good.to_dict()) + "\n"
        )
        store = GuidanceStore(tmp_path)
        records = store.load_all()
        assert len(records) == 1
        assert records[0].guidance_text == "Good"

    def test_load_all_skips_validation_invalid_records(self, tmp_path: Path):
        """Records with bad field values (e.g. unknown guidance_type) are skipped."""
        path = tmp_path / GUIDANCE_FILENAME
        bad_record = _make_guidance().to_dict()
        bad_record["guidance_type"] = "unknown_type"
        good = _make_guidance(guidance_text="Good")
        path.write_text(
            json.dumps(bad_record) + "\n" + json.dumps(good.to_dict()) + "\n"
        )
        store = GuidanceStore(tmp_path)
        records = store.load_all()
        assert len(records) == 1
        assert records[0].guidance_text == "Good"

    def test_load_for_target_returns_matching(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g1 = _make_guidance(target="hypothesis", gate_trigger=GateTrigger.BEFORE)
        g2 = _make_guidance(target="execute", gate_trigger=GateTrigger.BEFORE)
        g3 = _make_guidance(target="hypothesis", gate_trigger=GateTrigger.BEFORE)
        store.save(g1)
        store.save(g2)
        store.save(g3)
        records = store.load_for_target("research", "hypothesis", GateTrigger.BEFORE)
        assert len(records) == 2
        assert all(r.target == "hypothesis" for r in records)

    def test_load_for_target_filters_by_trigger(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g_before = _make_guidance(target="execute", gate_trigger=GateTrigger.BEFORE)
        g_after = _make_guidance(target="execute", gate_trigger=GateTrigger.AFTER)
        store.save(g_before)
        store.save(g_after)
        before_records = store.load_for_target("research", "execute", GateTrigger.BEFORE)
        after_records = store.load_for_target("research", "execute", GateTrigger.AFTER)
        assert len(before_records) == 1
        assert len(after_records) == 1

    def test_load_for_target_filters_by_sequence(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g0 = _make_guidance(target="hypothesis", gate_trigger=GateTrigger.BEFORE, sequence=0)
        g1 = _make_guidance(target="hypothesis", gate_trigger=GateTrigger.BEFORE, sequence=1)
        store.save(g0)
        store.save(g1)
        seq0 = store.load_for_target("research", "hypothesis", GateTrigger.BEFORE, sequence=0)
        seq1 = store.load_for_target("research", "hypothesis", GateTrigger.BEFORE, sequence=1)
        assert len(seq0) == 1
        assert seq0[0].sequence == 0
        assert len(seq1) == 1
        assert seq1[0].sequence == 1

    def test_load_for_target_returns_empty_for_no_match(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        store.save(_make_guidance(target="hypothesis"))
        assert store.load_for_target("research", "execute", GateTrigger.BEFORE) == []

    def test_load_for_target_filters_by_workflow(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        store.save(_make_guidance(workflow="research", target="hypothesis", gate_trigger=GateTrigger.BEFORE))
        store.save(_make_guidance(workflow="plan", target="hypothesis", gate_trigger=GateTrigger.BEFORE))
        research_only = store.load_for_target("research", "hypothesis", GateTrigger.BEFORE)
        assert len(research_only) == 1
        assert research_only[0].workflow == "research"

    def test_load_latest_returns_last_record(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        g1 = _make_guidance(guidance_text="First")
        g2 = _make_guidance(guidance_text="Last")
        store.save(g1)
        store.save(g2)
        latest = store.load_latest()
        assert latest is not None
        assert latest.guidance_text == "Last"

    def test_load_latest_returns_none_for_empty_store(self, tmp_path: Path):
        store = GuidanceStore(tmp_path)
        assert store.load_latest() is None

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "output"
        store = GuidanceStore(nested)
        store.save(_make_guidance())
        assert (nested / GUIDANCE_FILENAME).exists()


# ===========================================================================
# format_guidance_block
# ===========================================================================


class TestFormatGuidanceBlock:
    def test_empty_list_returns_empty_string(self):
        assert format_guidance_block([]) == ""

    def test_single_record_contains_guidance_text(self):
        g = _make_guidance(guidance_text="Use more data sources.")
        block = format_guidance_block([g])
        assert "Use more data sources." in block

    def test_single_record_contains_guidance_type(self):
        g = _make_guidance(guidance_type="steer")
        block = format_guidance_block([g])
        assert "steer" in block.lower()

    def test_single_record_contains_target(self):
        g = _make_guidance(target="execute")
        block = format_guidance_block([g])
        assert "execute" in block

    def test_single_record_contains_gate_trigger(self):
        g = _make_guidance(gate_trigger=GateTrigger.AFTER)
        block = format_guidance_block([g])
        assert "after" in block.lower()

    def test_multiple_records_all_appear(self):
        g1 = _make_guidance(guidance_text="First guidance.")
        g2 = _make_guidance(guidance_text="Second guidance.")
        block = format_guidance_block([g1, g2])
        assert "First guidance." in block
        assert "Second guidance." in block

    def test_guidance_text_is_stripped(self):
        g = _make_guidance(guidance_text="  trimmed  ")
        block = format_guidance_block([g])
        assert "trimmed" in block
        # Leading/trailing whitespace should be stripped
        assert "  trimmed  " not in block

    def test_block_has_header(self):
        g = _make_guidance()
        block = format_guidance_block([g])
        assert "Human Guidance" in block
