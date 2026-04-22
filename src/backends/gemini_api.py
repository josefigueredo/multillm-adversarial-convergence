"""Google Gemini direct API backend."""

from __future__ import annotations

from typing import Any

from .base_api import ApiBackend
import json

from .types import AgentResponse, BackendCapabilities, CallOptions, StreamEvent, ToolCallRequest


class GeminiApiBackend(ApiBackend):
    name = "gemini-api"
    api_key_env_vars = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_json_schema=False,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_streaming=True,
        supports_function_tools=True,
        supports_tools=False,
        default_model="gemini-2.5-flash",
    )

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        api_key = self._api_key()
        model = opts.model or self.capabilities.default_model
        method = "streamGenerateContent" if opts.stream else "generateContent"
        url = self._append_query_params(
            self._base_url(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}"),
            {"key": api_key},
        )
        if isinstance(prompt, list):
            contents = prompt
        else:
            contents = [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ],
                }
            ]
        body = {"contents": contents}
        if opts.system_prompt:
            body["system_instruction"] = {
                "parts": [
                    {
                        "text": opts.system_prompt,
                    }
                ]
            }
        if opts.tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.input_schema,
                        }
                        for tool in opts.tools
                    ]
                }
            ]
            if opts.tool_choice == "required" and opts.tools:
                body["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tool.name for tool in opts.tools],
                    }
                }
        return (
            url,
            {
                "Content-Type": "application/json",
            },
            body,
        )

    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        text_parts: list[str] = []
        for candidate in payload.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
        usage = payload.get("usageMetadata", {})
        return AgentResponse(
            text="".join(text_parts),
            cost_usd=0.0,
            is_error=bool(payload.get("error")),
            input_tokens=usage.get("promptTokenCount", 0),
            output_tokens=usage.get("candidatesTokenCount", 0),
            raw=payload,
        )

    def extract_function_tool_calls(self, payload: dict[str, Any]) -> list[ToolCallRequest]:
        calls: list[ToolCallRequest] = []
        for candidate in payload.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                if not isinstance(part, dict):
                    continue
                function_call = part.get("functionCall")
                if not isinstance(function_call, dict):
                    continue
                name = str(function_call.get("name", ""))
                calls.append(
                    ToolCallRequest(
                        id=name,
                        call_id=name,
                        name=name,
                        arguments_json=json.dumps(function_call.get("args", {})),
                        raw=part,
                    )
                )
        return calls

    def build_tool_followup_input(
        self,
        prompt: str,
        response_payload: dict[str, Any],
        tool_outputs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assistant_content = {"role": "model", "parts": []}
        candidates = response_payload.get("candidates", [])
        if candidates and isinstance(candidates[0], dict):
            assistant_content = candidates[0].get("content", assistant_content)
        return [
            {"role": "user", "parts": [{"text": prompt}]},
            assistant_content,
            {
                "role": "tool",
                "parts": [
                    {
                        "functionResponse": {
                            "name": item["call_id"],
                            "response": {"output": item["output"]},
                        }
                    }
                    for item in tool_outputs
                ],
            },
        ]

    def invoke_stream(self, prompt: str, opts: CallOptions, timeout: int = 300):
        started = False
        accumulated_text: list[str] = []
        usage: dict[str, Any] = {}

        for payload in self._post_stream(prompt, opts, timeout=timeout):
            if payload.get("error"):
                yield StreamEvent(type="error", raw=payload)
                continue

            parts: list[dict[str, str]] = []
            for candidate in payload.get("candidates", []):
                if not isinstance(candidate, dict):
                    continue
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    if isinstance(part, dict) and "text" in part:
                        parts.append({"text": str(part["text"])})

            if not started:
                started = True
                yield StreamEvent(type="start", raw=payload)

            text = "".join(part["text"] for part in parts)
            if text:
                accumulated_text.append(text)
                yield StreamEvent(type="text_delta", text=text, raw=payload)

            if isinstance(payload.get("usageMetadata"), dict):
                usage = payload["usageMetadata"]

        if started:
            yield StreamEvent(
                type="completed",
                raw={
                    "response": {
                        "candidates": [{"content": {"parts": [{"text": "".join(accumulated_text)}]}}],
                        "usageMetadata": usage,
                    }
                },
            )
