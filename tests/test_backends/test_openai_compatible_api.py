"""Tests for shared OpenAI-compatible API backend helpers."""

import json

from src.backends.openai_compatible_api import OpenAICompatibleResponsesApiBackend
from src.backends.types import BackendCapabilities, CallOptions, ToolDefinition


class _StubOpenAICompatibleBackend(OpenAICompatibleResponsesApiBackend):
    name = "stub-openai-compatible"
    api_key_env_vars = ("OPENAI_API_KEY",)
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_json_schema=True,
        supports_function_tools=True,
        supports_tools=False,
        default_model="gpt-test",
    )

    def default_service_base_url(self) -> str:
        return "https://api.example.com"


def test_openai_compatible_base_builds_default_request():
    backend = _StubOpenAICompatibleBackend()
    url, headers, body = backend.build_request("hello", CallOptions(model="gpt-test"))
    assert url == "https://api.example.com/v1/responses"
    assert headers["Content-Type"] == "application/json"
    assert body["model"] == "gpt-test"
    assert body["input"] == "hello"


def test_openai_compatible_base_adds_json_schema_format():
    backend = _StubOpenAICompatibleBackend()
    _, _, body = backend.build_request(
        "hello",
        CallOptions(model="gpt-test", json_schema={"type": "object"}),
    )
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["schema"]["type"] == "object"


def test_openai_compatible_base_respects_provider_base_url_override():
    backend = _StubOpenAICompatibleBackend()
    backend.provider_config = type("Provider", (), {"base_url": "https://gateway.example.com"})()
    url, _, _ = backend.build_request("hello", CallOptions(model="gpt-test"))
    assert url == "https://gateway.example.com/v1/responses"


def test_openai_compatible_base_adds_stream_flag():
    backend = _StubOpenAICompatibleBackend()
    _, _, body = backend.build_request("hello", CallOptions(model="gpt-test", stream=True))
    assert body["stream"] is True


def test_openai_compatible_base_adds_function_tools():
    backend = _StubOpenAICompatibleBackend()
    _, _, body = backend.build_request(
        "hello",
        CallOptions(
            model="gpt-test",
            tools=(ToolDefinition(type="function", name="echo", input_schema={"type": "object"}),),
            tool_choice="required",
        ),
    )
    assert body["tools"] == [
        {
            "type": "function",
            "name": "echo",
            "description": "",
            "parameters": {"type": "object"},
            "strict": True,
        }
    ]
    assert body["tool_choice"] == "required"


def test_openai_compatible_base_extracts_function_tool_calls():
    backend = _StubOpenAICompatibleBackend()
    calls = backend.extract_function_tool_calls(
        {
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
    )
    assert len(calls) == 1
    assert calls[0].call_id == "call_123"
