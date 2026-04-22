"""Tests for src.backends.copilot_api — CopilotApiBackend."""

import json
from unittest.mock import patch

from src.backends.copilot_api import CopilotApiBackend
from src.backends.types import CallOptions, ToolDefinition


class TestCopilotApiBackend:
    def setup_method(self):
        self.backend = CopilotApiBackend()

    def test_name(self):
        assert self.backend.name == "copilot-api"

    def test_build_request_without_org(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="openai/gpt-4.1"))
        assert url == "https://models.github.ai/inference/chat/completions"
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2026-03-10"
        assert body["model"] == "openai/gpt-4.1"
        assert body["messages"] == [{"role": "user", "content": "hello"}]

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="openai/gpt-4.1", system_prompt="You are precise."),
        )
        assert body["messages"][0] == {"role": "system", "content": "You are precise."}
        assert body["messages"][1] == {"role": "user", "content": "hello"}

    def test_build_request_with_org_and_json_schema(self):
        self.backend.provider_config = type(
            "Provider",
            (),
            {"organization": "acme", "api_version": "2026-03-10", "base_url": ""},
        )()
        url, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="openai/gpt-4.1",
                json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            ),
        )
        assert url == "https://models.github.ai/orgs/acme/inference/chat/completions"
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["type"] == "object"

    def test_build_request_with_function_tools(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="openai/gpt-4.1",
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
                "function": {
                    "name": "echo",
                    "description": "Echo a message.",
                    "parameters": {"type": "object", "properties": {"message": {"type": "string"}}},
                },
            }
        ]
        assert body["tool_choice"] == "required"

    def test_build_request_enables_stream_with_usage(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="openai/gpt-4.1", stream=True),
        )
        assert body["stream"] is True
        assert body["stream_options"] == {"include_usage": True}

    def test_parse_payload(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "hi",
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_extract_function_tool_calls(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"message": "hi"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }
        calls = self.backend.extract_function_tool_calls(payload)
        assert len(calls) == 1
        assert calls[0].call_id == "call_123"
        assert calls[0].name == "echo"

    def test_build_tool_followup_input(self):
        followup = self.backend.build_tool_followup_input(
            "hello",
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "echo",
                                        "arguments": "{\"message\":\"hi\"}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
            [
                {"type": "function_call_output", "call_id": "call_123", "output": "echo:hi"},
            ],
        )
        assert followup == [
            {"role": "user", "content": "hello"},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": "{\"message\":\"hi\"}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_123",
                "content": "echo:hi",
            },
        ]

    def test_extract_error_details_for_permission(self):
        details = self.backend.extract_error_details(
            {
                "error": {
                    "message": "Forbidden",
                    "code": "forbidden",
                }
            },
            403,
        )
        assert details["category"] == "permission"

    @patch.dict("os.environ", {"GITHUB_TOKEN": "x"}, clear=True)
    def test_check_available_with_github_token(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {"GH_TOKEN": "x"}, clear=True)
    def test_check_available_with_gh_token(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_without_token(self):
        assert self.backend.check_available() is False
