"""Tests for backend option normalization."""

from src.backend_options import apply_backend_capabilities, build_call_options
from src.backends import get_backend
from src.backends.types import CallOptions
from src.config import ExecutionConfig


def test_build_call_options_preserves_execution_defaults():
    opts = build_call_options(
        ExecutionConfig(
            model="sonnet",
            system_prompt="You are precise.",
            stream=True,
            allowed_tools="Read,WebSearch",
            max_turns=12,
            max_budget_per_call=0.75,
        )
    )
    assert opts.model == "sonnet"
    assert opts.system_prompt == "You are precise."
    assert opts.stream is True
    assert opts.allowed_tools == "Read,WebSearch"
    assert opts.max_turns == 12
    assert opts.max_budget_usd == 0.75


def test_apply_backend_capabilities_strips_tools_for_unsupported_backend():
    backend = get_backend("litellm-api")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="openai/gpt-4.1-mini", allowed_tools="Read,WebSearch"),
    )
    assert normalized.allowed_tools == ""


def test_apply_backend_capabilities_strips_json_schema_when_unsupported():
    backend = get_backend("bedrock-api")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            json_schema={"type": "object"},
        ),
    )
    assert normalized.json_schema is None


def test_apply_backend_capabilities_strips_system_prompt_when_unsupported():
    backend = get_backend("claude-cli")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="sonnet", system_prompt="You are precise."),
    )
    assert normalized.system_prompt == ""


def test_apply_backend_capabilities_preserves_system_prompt_when_supported():
    backend = get_backend("claude-api")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="claude-sonnet-4-5", system_prompt="You are precise."),
    )
    assert normalized.system_prompt == "You are precise."


def test_apply_backend_capabilities_preserves_json_schema_when_supported():
    backend = get_backend("copilot-api")
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="openai/gpt-4.1", json_schema=schema),
    )
    assert normalized.json_schema == schema


def test_apply_backend_capabilities_strips_stream_when_unsupported():
    backend = get_backend("claude-api")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="claude-sonnet-4-5", stream=True),
    )
    assert normalized.stream is False


def test_apply_backend_capabilities_preserves_stream_when_supported():
    backend = get_backend("litellm-api")
    normalized = apply_backend_capabilities(
        backend,
        CallOptions(model="openai/gpt-4.1-mini", stream=True),
    )
    assert normalized.stream is True
