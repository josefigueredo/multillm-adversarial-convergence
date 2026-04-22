"""Tests for src.backends.claude_api — ClaudeApiBackend."""

import json
from unittest.mock import patch

from src.backends import StreamEvent
from src.backends.claude_api import ClaudeApiBackend
from src.backends.types import CallOptions


class TestClaudeApiBackend:
    def setup_method(self):
        self.backend = ClaudeApiBackend()

    def test_name(self):
        assert self.backend.name == "claude-api"

    def test_build_request(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="opus"))
        assert url == "https://api.anthropic.com/v1/messages"
        assert headers["anthropic-version"] == "2023-06-01"
        assert body["model"] == "opus"
        assert body["messages"][0]["content"] == "hello"

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="opus", system_prompt="You are precise."),
        )
        assert body["system"] == "You are precise."

    def test_build_request_enables_stream(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="opus", stream=True),
        )
        assert body["stream"] is True

    def test_parse_payload(self):
        payload = {
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_extract_error_details_for_rate_limit(self):
        details = self.backend.extract_error_details(
            {
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "Too many requests",
                },
            },
            429,
        )
        assert details["category"] == "rate_limit"
        assert details["provider_code"] == "rate_limit_error"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "x"})
    def test_check_available_when_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_when_api_key_missing(self):
        assert self.backend.check_available() is False

    def test_invoke_stream_normalizes_anthropic_events(self):
        payloads = iter([
            {"type": "message_start", "message": {"content": []}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hel"}},
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "lo"}},
            {"type": "message_delta", "usage": {"output_tokens": 5}},
            {
                "type": "message_stop",
                "message": {
                    "content": [{"type": "text", "text": "Hello"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            },
        ])
        with patch.object(self.backend, "_post_stream", return_value=payloads):
            events = list(self.backend.invoke_stream("hello", CallOptions(model="opus", stream=True), timeout=20))

        assert events == [
            StreamEvent(type="start", raw={"type": "message_start", "message": {"content": []}}),
            StreamEvent(
                type="text_delta",
                text="Hel",
                raw={"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hel"}},
            ),
            StreamEvent(
                type="text_delta",
                text="lo",
                raw={"type": "content_block_delta", "delta": {"type": "text_delta", "text": "lo"}},
            ),
            StreamEvent(
                type="completed",
                raw={
                    "response": {
                        "content": [{"type": "text", "text": "Hello"}],
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                    }
                },
            ),
        ]

    def test_invoke_stream_maps_anthropic_error_event(self):
        payloads = iter([
            {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
        ])
        with patch.object(self.backend, "_post_stream", return_value=payloads):
            events = list(self.backend.invoke_stream("hello", CallOptions(model="opus", stream=True), timeout=20))
        assert events == [
            StreamEvent(
                type="error",
                raw={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
            ),
        ]
