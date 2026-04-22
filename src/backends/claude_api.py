"""Anthropic Claude direct API backend."""

from __future__ import annotations

from typing import Any

from .base_api import ApiBackend
from .types import AgentResponse, BackendCapabilities, CallOptions


class ClaudeApiBackend(ApiBackend):
    name = "claude-api"
    api_key_env_vars = ("ANTHROPIC_API_KEY",)
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_json_schema=False,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_tools=False,
        default_model="claude-sonnet-4-5",
    )

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        api_key = self._api_key()
        model = opts.model or self.capabilities.default_model
        body = {
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        if opts.system_prompt:
            body["system"] = opts.system_prompt
        return (
            self._base_url("https://api.anthropic.com/v1/messages"),
            {
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            body,
        )

    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        content = payload.get("content", [])
        text = ""
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        usage = payload.get("usage", {})
        return AgentResponse(
            text=text,
            cost_usd=0.0,
            is_error=bool(payload.get("error")),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=payload,
        )
