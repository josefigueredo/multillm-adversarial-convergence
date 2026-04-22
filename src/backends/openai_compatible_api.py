"""Shared base for OpenAI-compatible Responses API gateways."""

from __future__ import annotations

import os
from typing import Any

from .base_api import ApiBackend
from .types import AgentResponse, CallOptions, StreamEvent


class OpenAICompatibleResponsesApiBackend(ApiBackend):
    """Base class for gateway adapters that expose /v1/responses semantics."""

    supports_json_schema_format: bool = True

    def check_available(self) -> bool:
        return bool(self.service_base_url())

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        api_key = self._api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body: dict[str, Any] = {
            "model": opts.model or self.capabilities.default_model,
            "input": prompt,
        }
        if opts.stream:
            body["stream"] = True
        if opts.system_prompt:
            body["instructions"] = opts.system_prompt
        if self.supports_json_schema_format and opts.json_schema:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "schema": opts.json_schema,
                }
            }
        return (
            f"{self.service_base_url().rstrip('/')}/v1/responses",
            headers,
            body,
        )

    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        usage = payload.get("usage", {})
        return AgentResponse(
            text=payload.get("output_text", ""),
            cost_usd=0.0,
            is_error=bool(payload.get("error")),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            raw=payload,
        )

    def service_base_url(self) -> str:
        provider = getattr(self, "provider_config", None)
        base_url = getattr(provider, "base_url", "") if provider is not None else ""
        return base_url or self.default_service_base_url()

    def invoke_stream(self, prompt: str, opts: CallOptions, timeout: int = 300):
        for payload in self._post_stream(prompt, opts, timeout=timeout):
            event_type = str(payload.get("type", ""))
            if event_type == "response.created":
                yield StreamEvent(type="start", raw=payload)
            elif event_type == "response.output_text.delta":
                yield StreamEvent(type="text_delta", text=str(payload.get("delta", "")), raw=payload)
            elif event_type == "response.completed":
                yield StreamEvent(type="completed", raw=payload)
            elif event_type == "error":
                yield StreamEvent(type="error", raw=payload)

    def default_service_base_url(self) -> str:
        raise NotImplementedError
