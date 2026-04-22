"""Google Gemini direct API backend."""

from __future__ import annotations

from typing import Any

from .base_api import ApiBackend
from .types import AgentResponse, BackendCapabilities, CallOptions


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
        supports_tools=False,
        default_model="gemini-2.5-flash",
    )

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        api_key = self._api_key()
        model = opts.model or self.capabilities.default_model
        url = self._append_query_params(
            self._base_url(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"),
            {"key": api_key},
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }
        if opts.system_prompt:
            body["system_instruction"] = {
                "parts": [
                    {
                        "text": opts.system_prompt,
                    }
                ]
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
