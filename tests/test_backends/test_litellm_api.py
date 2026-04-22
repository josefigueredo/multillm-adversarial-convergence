"""Tests for src.backends.litellm_api — LiteLLMApiBackend."""

import json
from unittest.mock import patch

from src.backends.litellm_api import LiteLLMApiBackend
from src.backends.types import CallOptions, ToolDefinition


class TestLiteLLMApiBackend:
    def setup_method(self):
        self.backend = LiteLLMApiBackend()

    def test_name(self):
        assert self.backend.name == "litellm-api"

    def test_build_request_uses_local_default_base_url(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="openai/gpt-4.1-mini"))
        assert url == "http://localhost:4000/v1/responses"
        assert headers["Content-Type"] == "application/json"
        assert body["model"] == "openai/gpt-4.1-mini"
        assert body["input"] == "hello"

    def test_build_request_uses_provider_base_url_override(self):
        self.backend.provider_config = type("Provider", (), {"base_url": "https://litellm.example.com"})()
        url, _, _ = self.backend.build_request("hello", CallOptions(model="openai/gpt-4.1-mini"))
        assert url == "https://litellm.example.com/v1/responses"

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="openai/gpt-4.1-mini", system_prompt="You are precise."),
        )
        assert body["instructions"] == "You are precise."

    def test_build_request_with_json_schema(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="openai/gpt-4.1-mini",
                json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            ),
        )
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["schema"]["type"] == "object"

    def test_build_request_with_function_tools(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="openai/gpt-4.1-mini",
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

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_with_default_local_base_url(self):
        assert self.backend.check_available() is True
