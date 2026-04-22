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
