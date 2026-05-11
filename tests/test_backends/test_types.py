"""Tests for src.backends.types — AgentResponse, CallOptions, BackendCapabilities."""

import pytest

from src.backends.types import (
    AgentResponse,
    BackendCapabilities,
    CallOptions,
    StreamEvent,
    ToolCallRequest,
    ToolDefinition,
    ToolResult,
)


class TestAgentResponse:
    def test_frozen(self):
        r = AgentResponse(text="hi", cost_usd=0.01, is_error=False)
        with pytest.raises(AttributeError):
            r.text = "changed"

    def test_defaults(self):
        r = AgentResponse(text="", cost_usd=0.0, is_error=False)
        assert r.raw == {}
        assert r.input_tokens == 0
        assert r.output_tokens == 0

    def test_with_meta_returns_new_instance(self):
        """``with_meta`` must NOT mutate the receiver — the freeze is real."""
        original = AgentResponse(text="hi", cost_usd=0.01, is_error=False, raw={"a": 1})
        decorated = original.with_meta(retry_attempts=2)

        assert decorated is not original
        assert original.raw == {"a": 1}, "original.raw was mutated"
        assert decorated.raw == {"a": 1, "retry_attempts": 2}

    def test_with_meta_preserves_core_fields(self):
        original = AgentResponse(
            text="findings", cost_usd=0.05, is_error=False,
            input_tokens=100, output_tokens=50,
        )
        decorated = original.with_meta(tool_loop={"turns": 3})

        assert decorated.text == "findings"
        assert decorated.cost_usd == 0.05
        assert decorated.is_error is False
        assert decorated.input_tokens == 100
        assert decorated.output_tokens == 50
        assert decorated.raw == {"tool_loop": {"turns": 3}}

    def test_with_meta_later_keys_overwrite_earlier(self):
        original = AgentResponse(text="x", cost_usd=0.0, is_error=False, raw={"k": 1})
        assert original.with_meta(k=2).raw == {"k": 2}


class TestCallOptions:
    def test_defaults(self):
        opts = CallOptions()
        assert opts.model == ""
        assert opts.system_prompt == ""
        assert opts.stream is False
        assert opts.tools == ()
        assert opts.tool_choice == "auto"
        assert opts.allowed_tools == ""
        assert opts.max_turns == 10
        assert opts.max_budget_usd == 0.0
        assert opts.json_schema is None


class TestToolDefinition:
    def test_defaults(self):
        tool = ToolDefinition(type="function", name="echo")
        assert tool.description == ""
        assert tool.input_schema == {}
        assert tool.strict is True


class TestToolCallRequest:
    def test_defaults(self):
        call = ToolCallRequest(call_id="call_123", name="echo", arguments_json='{"message":"hi"}')
        assert call.id == ""
        assert call.raw == {}


class TestToolResult:
    def test_defaults(self):
        result = ToolResult(call_id="call_123", name="echo", output="hi")
        assert result.is_error is False
        assert result.raw == {}


class TestStreamEvent:
    def test_defaults(self):
        event = StreamEvent(type="text_delta")
        assert event.text == ""
        assert event.raw == {}


class TestBackendCapabilities:
    def test_defaults(self):
        cap = BackendCapabilities()
        assert cap.transport == "cli"
        assert cap.provider_kind == "direct"
        assert cap.supports_json_schema is False
        assert cap.supports_budget_cap is False
        assert cap.supports_rate_limit_detection is False
        assert cap.supports_system_prompt is False
        assert cap.supports_streaming is False
        assert cap.supports_response_format is False
        assert cap.supports_org_routing is False
        assert cap.supports_function_tools is False
        assert cap.supports_tools is True
        assert cap.default_model == ""

    def test_frozen(self):
        cap = BackendCapabilities()
        with pytest.raises(AttributeError):
            cap.default_model = "changed"
