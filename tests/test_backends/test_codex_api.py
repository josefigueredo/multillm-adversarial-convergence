"""Tests for src.backends.codex_api — CodexApiBackend."""

import json
from unittest.mock import patch

from src.backends.codex_api import CodexApiBackend
from src.backends.types import CallOptions, ToolDefinition


class TestCodexApiBackend:
    def setup_method(self):
        self.backend = CodexApiBackend()

    def test_name(self):
        assert self.backend.name == "codex-api"

    def test_build_request(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="gpt-5.4"))
        assert url == "https://api.openai.com/v1/responses"
        assert headers["Authorization"].startswith("Bearer ")
        assert body["model"] == "gpt-5.4"
        assert body["input"] == "hello"

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="gpt-5.4", system_prompt="You are precise."),
        )
        assert body["instructions"] == "You are precise."

    def test_build_request_uses_provider_base_url_override(self):
        self.backend.provider_config = type("Provider", (), {"base_url": "https://litellm.example.com"})()
        url, _, _ = self.backend.build_request("hello", CallOptions(model="gpt-5.4"))
        assert url == "https://litellm.example.com/v1/responses"

    def test_build_request_with_json_schema(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="gpt-5.4", json_schema={"type": "object"}),
        )
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["schema"]["type"] == "object"

    def test_build_request_with_function_tools(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="gpt-5.4",
                tools=(
                    ToolDefinition(
                        type="function",
                        name="echo",
                        description="Echo a message.",
                        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
                    ),
                ),
                tool_choice="required",
            ),
        )
        assert body["tools"] == [
            {
                "type": "function",
                "name": "echo",
                "description": "Echo a message.",
                "parameters": {"type": "object", "properties": {"message": {"type": "string"}}},
                "strict": True,
            }
        ]
        assert body["tool_choice"] == "required"

    def test_parse_payload(self):
        payload = {
            "output_text": "hi",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_extract_error_details_for_insufficient_quota(self):
        details = self.backend.extract_error_details(
            {
                "error": {
                    "message": "Quota exceeded",
                    "code": "insufficient_quota",
                }
            },
            429,
        )
        assert details["category"] == "quota"
        assert details["provider_code"] == "insufficient_quota"

    def test_invoke_posts_and_parses_payload(self):
        with patch.object(self.backend, "_post_json", return_value={
            "output_text": "hi",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }) as mock_post:
            resp = self.backend.invoke("hello", CallOptions(model="gpt-5.4"), timeout=15)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5
        mock_post.assert_called_once()

    def test_extract_function_tool_calls(self):
        payload = {
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "echo",
                    "arguments": json.dumps({"message": "hi"}),
                }
            ]
        }
        calls = self.backend.extract_function_tool_calls(payload)
        assert len(calls) == 1
        assert calls[0].call_id == "call_123"
        assert calls[0].name == "echo"
        assert calls[0].arguments_json == '{"message": "hi"}'

    @patch.dict("os.environ", {"OPENAI_API_KEY": "x"})
    def test_check_available_when_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_when_api_key_missing(self):
        assert self.backend.check_available() is False
