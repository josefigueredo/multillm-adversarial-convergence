"""Tests for normalized streaming on copilot-api."""

from unittest.mock import patch

from src.backends import StreamEvent
from src.backends.copilot_api import CopilotApiBackend
from src.backends.types import CallOptions


def test_copilot_invoke_stream_normalizes_chat_completion_chunks():
    backend = CopilotApiBackend()
    payloads = iter([
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    ])

    with patch.object(backend, "_post_stream", return_value=payloads):
        events = list(backend.invoke_stream("hello", CallOptions(model="openai/gpt-4.1", stream=True), timeout=20))

    assert events == [
        StreamEvent(type="start", raw={"choices": [{"delta": {"role": "assistant"}}]}),
        StreamEvent(type="text_delta", text="Hel", raw={"choices": [{"delta": {"content": "Hel"}}]}),
        StreamEvent(type="text_delta", text="lo", raw={"choices": [{"delta": {"content": "lo"}}]}),
        StreamEvent(
            type="completed",
            raw={
                "response": {
                    "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            },
        ),
    ]


def test_copilot_invoke_stream_maps_error_event():
    backend = CopilotApiBackend()
    payloads = iter([
        {"error": {"message": "boom", "code": "forbidden"}},
    ])

    with patch.object(backend, "_post_stream", return_value=payloads):
        events = list(backend.invoke_stream("hello", CallOptions(model="openai/gpt-4.1", stream=True), timeout=20))

    assert events == [
        StreamEvent(type="error", raw={"error": {"message": "boom", "code": "forbidden"}}),
    ]
