"""GitHub Models-backed API adapter exposed as copilot-api."""

from __future__ import annotations

from typing import Any

from .base_api import ApiBackend
from .types import AgentResponse, BackendCapabilities, CallOptions, StreamEvent, ToolCallRequest


class CopilotApiBackend(ApiBackend):
    name = "copilot-api"
    api_key_env_vars = ("GITHUB_TOKEN", "GH_TOKEN")
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="aggregator",
        supports_json_schema=True,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_streaming=True,
        supports_response_format=True,
        supports_org_routing=True,
        supports_function_tools=True,
        supports_tools=False,
        default_model="openai/gpt-4.1",
    )

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        provider = getattr(self, "provider_config", None)
        organization = getattr(provider, "organization", "") if provider is not None else ""
        api_version = getattr(provider, "api_version", "") if provider is not None else ""
        api_version = api_version or "2026-03-10"
        base_url = self._base_url("https://models.github.ai")
        path = "/inference/chat/completions"
        if organization:
            path = f"/orgs/{organization}{path}"
        if isinstance(prompt, list):
            messages = prompt
        else:
            messages: list[dict[str, Any]] = []
            if opts.system_prompt:
                messages.append({"role": "system", "content": opts.system_prompt})
            messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": opts.model or self.capabilities.default_model,
            "messages": messages,
        }
        if opts.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in opts.tools
            ]
            body["tool_choice"] = opts.tool_choice
        if opts.stream:
            body["stream"] = True
            body["stream_options"] = {"include_usage": True}
        if opts.json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": opts.json_schema,
            }
        return (
            f"{base_url.rstrip('/')}{path}",
            {
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._api_key()}",
                "X-GitHub-Api-Version": api_version,
            },
            body,
        )

    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        text = ""
        choices = payload.get("choices", [])
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message", {})
            text = message.get("content", "")
        usage = payload.get("usage", {})
        return AgentResponse(
            text=text,
            cost_usd=0.0,
            is_error=bool(payload.get("error")),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            raw=payload,
        )

    def extract_function_tool_calls(self, payload: dict[str, Any]) -> list[ToolCallRequest]:
        calls: list[ToolCallRequest] = []
        choices = payload.get("choices", [])
        if not choices or not isinstance(choices[0], dict):
            return calls
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            return calls
        for item in message.get("tool_calls", []):
            if not isinstance(item, dict) or item.get("type") != "function":
                continue
            fn = item.get("function", {})
            if not isinstance(fn, dict):
                continue
            calls.append(
                ToolCallRequest(
                    id=str(item.get("id", "")),
                    call_id=str(item.get("id", "")),
                    name=str(fn.get("name", "")),
                    arguments_json=str(fn.get("arguments", "")),
                    raw=item,
                )
            )
        return calls

    def build_tool_followup_input(
        self,
        prompt: str,
        response_payload: dict[str, Any],
        tool_outputs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        choices = response_payload.get("choices", [])
        assistant_message = {}
        if choices and isinstance(choices[0], dict):
            assistant_message = choices[0].get("message", {})
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": prompt},
            assistant_message,
        ]
        for item in tool_outputs:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": item["call_id"],
                    "content": item["output"],
                }
            )
        return messages

    def invoke_stream(self, prompt: str, opts: CallOptions, timeout: int = 300):
        accumulated_text: list[str] = []
        usage: dict[str, Any] = {}
        started = False

        for payload in self._post_stream(prompt, opts, timeout=timeout):
            if payload.get("error"):
                yield StreamEvent(type="error", raw=payload)
                continue

            choices = payload.get("choices", [])
            if not isinstance(choices, list) or not choices:
                continue

            choice = choices[0] if isinstance(choices[0], dict) else {}
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
            if not started:
                started = True
                yield StreamEvent(type="start", raw=payload)

            content = ""
            if isinstance(delta, dict):
                content = str(delta.get("content", "") or "")
            if content:
                accumulated_text.append(content)
                yield StreamEvent(type="text_delta", text=content, raw=payload)

            if isinstance(payload.get("usage"), dict):
                usage = payload["usage"]

            if choice.get("finish_reason"):
                yield StreamEvent(
                    type="completed",
                    raw={
                        "response": {
                            "choices": [
                                {
                                    "message": {
                                        "role": "assistant",
                                        "content": "".join(accumulated_text),
                                    }
                                }
                            ],
                            "usage": usage,
                        }
                    },
                )
