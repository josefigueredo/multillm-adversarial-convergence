"""GitHub Models-backed API adapter exposed as copilot-api."""

from __future__ import annotations

from typing import Any

from .base_api import ApiBackend
from .types import AgentResponse, BackendCapabilities, CallOptions


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
        supports_response_format=True,
        supports_org_routing=True,
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
        messages: list[dict[str, str]] = []
        if opts.system_prompt:
            messages.append({"role": "system", "content": opts.system_prompt})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": opts.model or self.capabilities.default_model,
            "messages": messages,
        }
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
