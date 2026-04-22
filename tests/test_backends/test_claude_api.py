"""Tests for src.backends.claude_api — ClaudeApiBackend."""

import json
from unittest.mock import patch

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
