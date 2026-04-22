"""Tests for direct API backend metadata."""

from src.backends import get_backend


def test_direct_api_backends_have_api_transport_metadata():
    for name in ("claude-api", "codex-api", "gemini-api"):
        backend = get_backend(name)
        assert backend.capabilities.transport == "api"
        assert backend.capabilities.provider_kind == "direct"
        assert backend.capabilities.supports_tools is False


def test_direct_api_capability_details():
    codex = get_backend("codex-api")
    assert codex.capabilities.supports_json_schema is True
    assert codex.capabilities.supports_system_prompt is True
    assert codex.capabilities.supports_streaming is True
    assert codex.capabilities.supports_response_format is True
    assert codex.capabilities.supports_org_routing is False


def test_api_backends_with_system_prompt_support():
    for name in ("claude-api", "codex-api", "gemini-api", "litellm-api", "copilot-api", "bedrock-api"):
        backend = get_backend(name)
        assert backend.capabilities.supports_system_prompt is True


def test_claude_and_gemini_api_support_streaming():
    for name in ("claude-api", "gemini-api"):
        backend = get_backend(name)
        assert backend.capabilities.supports_streaming is True


def test_litellm_api_has_aggregator_metadata():
    backend = get_backend("litellm-api")
    assert backend.capabilities.transport == "api"
    assert backend.capabilities.provider_kind == "aggregator"
    assert backend.capabilities.supports_json_schema is True
    assert backend.capabilities.supports_streaming is True
    assert backend.capabilities.supports_response_format is True
    assert backend.capabilities.supports_org_routing is False
    assert backend.capabilities.supports_tools is False


def test_bedrock_and_copilot_api_have_aggregator_metadata():
    for name in ("bedrock-api", "copilot-api"):
        backend = get_backend(name)
        assert backend.capabilities.transport == "api"
        assert backend.capabilities.provider_kind == "aggregator"


def test_copilot_api_supports_org_routing_and_response_format():
    backend = get_backend("copilot-api")
    assert backend.capabilities.supports_response_format is True
    assert backend.capabilities.supports_org_routing is True
    assert backend.capabilities.supports_streaming is True


def test_bedrock_api_does_not_support_response_format_or_org_routing():
    backend = get_backend("bedrock-api")
    assert backend.capabilities.supports_response_format is False
    assert backend.capabilities.supports_org_routing is False
    assert backend.capabilities.supports_streaming is True
