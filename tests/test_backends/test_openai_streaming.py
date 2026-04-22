"""Tests for normalized streaming on OpenAI-compatible API backends."""

from unittest.mock import patch

from src.backends import StreamEvent
from src.backends.litellm_api import LiteLLMApiBackend
from src.backends.types import CallOptions


def test_openai_compatible_invoke_stream_normalizes_text_events():
    backend = LiteLLMApiBackend()
    payloads = iter([
        {"type": "response.created"},
        {"type": "response.output_text.delta", "delta": "Hel"},
        {"type": "response.output_text.delta", "delta": "lo"},
        {"type": "response.completed"},
    ])
    with patch.object(backend, "_post_stream", return_value=payloads):
        events = list(backend.invoke_stream("hello", CallOptions(model="openai/gpt-4.1-mini", stream=True), timeout=20))
    assert events == [
        StreamEvent(type="start", raw={"type": "response.created"}),
        StreamEvent(type="text_delta", text="Hel", raw={"type": "response.output_text.delta", "delta": "Hel"}),
        StreamEvent(type="text_delta", text="lo", raw={"type": "response.output_text.delta", "delta": "lo"}),
        StreamEvent(type="completed", raw={"type": "response.completed"}),
    ]


def test_openai_compatible_invoke_stream_maps_error_event():
    backend = LiteLLMApiBackend()
    payloads = iter([
        {"type": "error", "message": "boom"},
    ])
    with patch.object(backend, "_post_stream", return_value=payloads):
        events = list(backend.invoke_stream("hello", CallOptions(model="openai/gpt-4.1-mini", stream=True), timeout=20))
    assert events == [
        StreamEvent(type="error", raw={"type": "error", "message": "boom"}),
    ]
