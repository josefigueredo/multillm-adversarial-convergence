"""Tests for src.backends.gemini_api — GeminiApiBackend."""

import json
from unittest.mock import patch

from src.backends import StreamEvent
from src.backends.gemini_api import GeminiApiBackend
from src.backends.types import CallOptions, ToolDefinition


class TestGeminiApiBackend:
    def setup_method(self):
        self.backend = GeminiApiBackend()

    def test_name(self):
        assert self.backend.name == "gemini-api"

    def test_build_request(self):
        url, headers, body = self.backend.build_request("hello", CallOptions(model="gemini-2.5-pro"))
        assert url.startswith("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent")
        assert headers["Content-Type"] == "application/json"
        assert body["contents"][0]["parts"][0]["text"] == "hello"

    def test_build_request_with_system_prompt(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(model="gemini-2.5-pro", system_prompt="You are precise."),
        )
        assert body["system_instruction"]["parts"][0]["text"] == "You are precise."

    def test_build_request_with_function_tools(self):
        _, _, body = self.backend.build_request(
            "hello",
            CallOptions(
                model="gemini-2.5-pro",
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
                "functionDeclarations": [
                    {
                        "name": "echo",
                        "description": "Echo a message.",
                        "parameters": {"type": "object", "properties": {"message": {"type": "string"}}},
                    }
                ]
            }
        ]
        assert body["toolConfig"]["functionCallingConfig"] == {
            "mode": "ANY",
            "allowedFunctionNames": ["echo"],
        }

    def test_build_stream_request_uses_stream_endpoint(self):
        url, _, _ = self.backend.build_request(
            "hello",
            CallOptions(model="gemini-2.5-pro", stream=True),
        )
        assert ":streamGenerateContent" in url

    def test_parse_payload(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "hi"}],
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
            },
        }
        resp = self.backend.parse_payload(payload)
        assert resp.text == "hi"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_extract_function_tool_calls(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "echo",
                                    "args": {"message": "hi"},
                                }
                            }
                        ]
                    }
                }
            ]
        }
        calls = self.backend.extract_function_tool_calls(payload)
        assert len(calls) == 1
        assert calls[0].call_id == "echo"
        assert calls[0].name == "echo"
        assert calls[0].arguments_json == '{"message": "hi"}'

    def test_build_tool_followup_input(self):
        followup = self.backend.build_tool_followup_input(
            "hello",
            {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "echo",
                                        "args": {"message": "hi"},
                                    }
                                }
                            ],
                        }
                    }
                ]
            },
            [
                {"type": "function_call_output", "call_id": "echo", "output": "echo:hi"},
            ],
        )
        assert followup == [
            {"role": "user", "parts": [{"text": "hello"}]},
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": "echo",
                            "args": {"message": "hi"},
                        }
                    }
                ],
            },
            {
                "role": "tool",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "echo",
                            "response": {"output": "echo:hi"},
                        }
                    }
                ],
            },
        ]

    def test_extract_error_details_for_unavailable(self):
        details = self.backend.extract_error_details(
            {
                "error": {
                    "code": 503,
                    "message": "The model is overloaded. Please try again later.",
                    "status": "UNAVAILABLE",
                }
            },
            503,
        )
        assert details["category"] == "server_error"
        assert details["provider_status"] == "UNAVAILABLE"

    @patch.dict("os.environ", {"GEMINI_API_KEY": "x"}, clear=True)
    def test_check_available_when_gemini_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "x"}, clear=True)
    def test_check_available_when_google_api_key_present(self):
        assert self.backend.check_available() is True

    @patch.dict("os.environ", {}, clear=True)
    def test_check_available_when_api_key_missing(self):
        assert self.backend.check_available() is False

    def test_invoke_stream_normalizes_gemini_chunks(self):
        payloads = iter([
            {"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "lo"}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}},
        ])
        with patch.object(self.backend, "_post_stream", return_value=payloads):
            events = list(self.backend.invoke_stream("hello", CallOptions(model="gemini-2.5-pro", stream=True), timeout=20))

        assert events == [
            StreamEvent(type="start", raw={"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]}),
            StreamEvent(
                type="text_delta",
                text="Hel",
                raw={"candidates": [{"content": {"parts": [{"text": "Hel"}]}}]},
            ),
            StreamEvent(
                type="text_delta",
                text="lo",
                raw={
                    "candidates": [{"content": {"parts": [{"text": "lo"}]}}],
                    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
                },
            ),
            StreamEvent(
                type="completed",
                raw={
                    "response": {
                        "candidates": [{"content": {"parts": [{"text": "Hello"}]}}],
                        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
                    }
                },
            ),
        ]

    def test_invoke_stream_maps_gemini_error_event(self):
        payloads = iter([
            {"error": {"status": "UNAVAILABLE", "message": "Overloaded"}},
        ])
        with patch.object(self.backend, "_post_stream", return_value=payloads):
            events = list(self.backend.invoke_stream("hello", CallOptions(model="gemini-2.5-pro", stream=True), timeout=20))
        assert events == [
            StreamEvent(type="error", raw={"error": {"status": "UNAVAILABLE", "message": "Overloaded"}}),
        ]
