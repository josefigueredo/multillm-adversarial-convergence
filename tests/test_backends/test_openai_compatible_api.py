"""Tests for shared OpenAI-compatible API backend helpers."""

from src.backends.openai_compatible_api import OpenAICompatibleResponsesApiBackend
from src.backends.types import BackendCapabilities, CallOptions


class _StubOpenAICompatibleBackend(OpenAICompatibleResponsesApiBackend):
    name = "stub-openai-compatible"
    api_key_env_vars = ("OPENAI_API_KEY",)
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_json_schema=True,
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
