"""Tests for the OOM-prevent / graceful-degrade paths in compress.

Three paths under test:
  1. low-memory pre-flight → truncation (no backend call)
  2. backend exception     → truncation (logged + audit event)
  3. backend empty/error   → truncation
And the happy path: backend returns content → state updated, no truncation.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from src.research_loop import (
    LoopContext,
    LoopState,
    _available_memory_gb,
    _compress_knowledge_base,
    _truncate_knowledge_base,
)


# ---------------------------------------------------------------------------
# Helpers — minimal LoopContext / LoopState for compress-only tests
# ---------------------------------------------------------------------------

class CapturingAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append({"event": event, **fields})

    @contextmanager
    def step(self, step: str, *, artifact_root=None, **fields):
        yield


def _make_state(tmp_path: Path, word_count: int) -> LoopState:
    """Build a LoopState whose knowledge_base is `word_count` words long."""
    state = LoopState()
    state.knowledge_base = " ".join(f"word{i}" for i in range(word_count))
    state.kb_path = tmp_path / "knowledge_base.md"
    state.kb_path.write_text(state.knowledge_base, encoding="utf-8")
    state.iteration = 5
    return state


def _make_ctx(audit, call_response=None, call_raises=None) -> LoopContext:
    backend = MagicMock(name="compress_backend")
    backend.name = "test-utility"

    strategy = MagicMock()
    strategy.get_compress_backend.return_value = backend

    if call_raises is not None:
        call_with = MagicMock(side_effect=call_raises)
    else:
        call_with = MagicMock(return_value=call_response)

    config = MagicMock()
    return LoopContext(
        call_with=call_with,
        invoke_for_strategy=lambda *a, **kw: None,
        track_usage=lambda *a, **kw: None,
        track_cost=lambda *a, **kw: None,
        config=config,
        strategy=strategy,
        track_candidate_usage=lambda *a, **kw: None,
        collect_provenance=lambda *a, **kw: None,
        methodology_summary=lambda: "",
        kb_summary=lambda: "",
        format_dimension_list=lambda l: ", ".join(l),
        goal_constraints_summary=lambda: "",
        audit_trail=audit,
        artifact_root=Path("."),
    )


# ---------------------------------------------------------------------------
# _truncate_knowledge_base — pure function, no mocks needed
# ---------------------------------------------------------------------------

def test_truncate_no_op_when_under_limit(tmp_path):
    state = _make_state(tmp_path, word_count=100)
    state.KB_MAX_WORDS = 8000
    original = state.knowledge_base

    _truncate_knowledge_base(state, reason="test")

    assert state.knowledge_base == original


def test_truncate_keeps_head_and_tail_drops_middle(tmp_path):
    state = _make_state(tmp_path, word_count=20000)
    state.KB_MAX_WORDS = 8000

    _truncate_knowledge_base(state, reason="test")

    # Should fit roughly under KB_MAX_WORDS (plus the marker line).
    final_words = state.knowledge_base.split()
    assert len(final_words) <= state.KB_MAX_WORDS + 20  # + marker line
    # Head retained (word0)
    assert "word0" in state.knowledge_base
    # Tail retained (word19999)
    assert "word19999" in state.knowledge_base
    # Marker present, mentions reason
    assert "trimmed by lossy fallback" in state.knowledge_base
    assert "test" in state.knowledge_base
    # Persisted to disk
    on_disk = state.kb_path.read_text(encoding="utf-8")
    assert on_disk == state.knowledge_base


# ---------------------------------------------------------------------------
# Pre-flight memory guard
# ---------------------------------------------------------------------------

def test_compress_skipped_when_memory_low(tmp_path, monkeypatch):
    """Layer 1: free RAM under threshold → truncation, no backend call."""
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    ctx = _make_ctx(audit)

    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: 0.5)

    _compress_knowledge_base(ctx, state)

    # Backend was never called
    ctx.call_with.assert_not_called()
    # Audit event recorded
    assert any(e["event"] == "compress_skipped_low_memory" for e in audit.events)
    skip_event = next(e for e in audit.events if e["event"] == "compress_skipped_low_memory")
    assert skip_event["free_gb"] == 0.5
    assert skip_event["corpus_words"] == 15000
    # Corpus was truncated
    assert "trimmed by lossy fallback" in state.knowledge_base


def test_compress_proceeds_when_memory_unknown(tmp_path, monkeypatch):
    """If detection fails (returns None), don't block compress on a guess."""
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    fake_resp = MagicMock(is_error=False, text=" ".join(f"compressed{i}" for i in range(500)))
    ctx = _make_ctx(audit, call_response=fake_resp)

    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: None)

    _compress_knowledge_base(ctx, state)

    # Backend WAS called (no skip)
    ctx.call_with.assert_called_once()
    # Corpus replaced with backend response
    assert "compressed0" in state.knowledge_base
    assert "trimmed by lossy fallback" not in state.knowledge_base


# ---------------------------------------------------------------------------
# Graceful degrade — backend errors fall back to truncation
# ---------------------------------------------------------------------------

def test_compress_fallback_on_backend_exception(tmp_path, monkeypatch):
    """Layer 2: backend raises → truncation + audit event."""
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    ctx = _make_ctx(audit, call_raises=RuntimeError("simulated backend explosion"))

    # Plenty of free memory so we exercise the layer-2 path, not layer-1
    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: 16.0)

    _compress_knowledge_base(ctx, state)

    ctx.call_with.assert_called_once()
    fallback_events = [e for e in audit.events if e["event"] == "compress_failed_fallback_truncate"]
    assert len(fallback_events) == 1
    assert "RuntimeError" in fallback_events[0]["error"]
    assert "trimmed by lossy fallback" in state.knowledge_base


def test_compress_fallback_on_empty_response(tmp_path, monkeypatch):
    """Layer 2: backend returns empty/short text → truncation + audit event."""
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    fake_resp = MagicMock(is_error=False, text="too short")  # < 200 chars threshold
    ctx = _make_ctx(audit, call_response=fake_resp)

    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: 16.0)

    _compress_knowledge_base(ctx, state)

    fallback_events = [e for e in audit.events if e["event"] == "compress_failed_fallback_truncate"]
    assert len(fallback_events) == 1
    assert fallback_events[0]["error"] == "empty_or_error_response"
    assert "trimmed by lossy fallback" in state.knowledge_base


def test_compress_fallback_on_is_error_response(tmp_path, monkeypatch):
    """Layer 2: backend returns is_error=True → truncation + audit event."""
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    fake_resp = MagicMock(is_error=True, text="long enough to pass the 200-char check " * 10)
    ctx = _make_ctx(audit, call_response=fake_resp)

    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: 16.0)

    _compress_knowledge_base(ctx, state)

    fallback_events = [e for e in audit.events if e["event"] == "compress_failed_fallback_truncate"]
    assert len(fallback_events) == 1
    assert "trimmed by lossy fallback" in state.knowledge_base


# ---------------------------------------------------------------------------
# Happy path — backend returns valid content
# ---------------------------------------------------------------------------

def test_compress_happy_path_replaces_corpus(tmp_path, monkeypatch):
    state = _make_state(tmp_path, word_count=15000)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    fake_resp = MagicMock(is_error=False, text=" ".join(f"summary{i}" for i in range(500)))
    ctx = _make_ctx(audit, call_response=fake_resp)

    monkeypatch.setattr("src.research_loop._available_memory_gb", lambda: 16.0)

    _compress_knowledge_base(ctx, state)

    ctx.call_with.assert_called_once()
    # Corpus is the backend's text (not the original, not truncated)
    assert state.knowledge_base.startswith("summary0 ")
    assert "trimmed by lossy fallback" not in state.knowledge_base
    # No fallback event was emitted
    assert not any(e["event"] == "compress_failed_fallback_truncate" for e in audit.events)
    assert not any(e["event"] == "compress_skipped_low_memory" for e in audit.events)


def test_compress_no_op_when_under_limit(tmp_path, monkeypatch):
    """Below KB_MAX_WORDS → no compress, no truncation, no audit events."""
    state = _make_state(tmp_path, word_count=100)
    state.KB_MAX_WORDS = 8000
    audit = CapturingAudit()
    ctx = _make_ctx(audit)
    original = state.knowledge_base

    _compress_knowledge_base(ctx, state)

    ctx.call_with.assert_not_called()
    assert state.knowledge_base == original
    assert audit.events == []


# ---------------------------------------------------------------------------
# _available_memory_gb — sanity check it returns a positive number on this host
# ---------------------------------------------------------------------------

def test_available_memory_returns_positive_number():
    """On any supported platform, the function should return a usable number
    (psutil installed → always works). None is acceptable too — that's the
    'unknown, don't block' contract — but we expect a number on dev hosts."""
    free_gb = _available_memory_gb()
    assert free_gb is None or free_gb > 0, "free RAM should be positive when known"
