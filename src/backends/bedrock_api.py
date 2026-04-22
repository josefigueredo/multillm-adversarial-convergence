"""Amazon Bedrock Converse adapter."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

from .base import Backend
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode


class BedrockApiBackend(Backend):
    name = "bedrock-api"
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="aggregator",
        supports_json_schema=False,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_tools=False,
        default_model="",
    )

    def cli_executable(self) -> str:
        return ""

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        return []

    def parse_response(self, stdout: str) -> AgentResponse:
        return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        text_parts: list[str] = []
        output = payload.get("output", {})
        message = output.get("message", {})
        for block in message.get("content", []):
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        usage = payload.get("usage", {})
        return AgentResponse(
            text="".join(text_parts),
            cost_usd=0.0,
            is_error=bool(payload.get("error")),
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            raw=payload,
        )

    def check_available(self) -> bool:
        return self._has_boto3() and bool(self._region())

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        model = opts.model or self.capabilities.default_model
        if not model:
            return AgentResponse(text="", cost_usd=0.0, is_error=True)
        try:
            client = self._client(region=self._region(), profile=self._aws_profile(), timeout=timeout)
            request: dict[str, Any] = {
                "modelId": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "text": prompt,
                            }
                        ],
                    }
                ],
            }
            if opts.system_prompt:
                request["system"] = [{"text": opts.system_prompt}]
            payload = client.converse(**request)
            return self.parse_payload(payload)
        except Exception as exc:
            return self._error_response_from_exception(exc)

    def _region(self) -> str:
        provider = getattr(self, "provider_config", None)
        region = getattr(provider, "region", "") if provider is not None else ""
        return region or os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")

    def _aws_profile(self) -> str:
        provider = getattr(self, "provider_config", None)
        return getattr(provider, "aws_profile", "") if provider is not None else ""

    @staticmethod
    def _error_response_from_exception(exc: Exception) -> AgentResponse:
        response = getattr(exc, "response", {}) or {}
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        provider_code = str(error.get("Code", ""))
        message = str(error.get("Message", "") or str(exc) or "Bedrock request failed")
        category = BedrockApiBackend._classify_error(provider_code)
        return AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=True,
            raw={
                "error": {
                    "category": category,
                    "message": message,
                    "provider_code": provider_code,
                    "exception_type": type(exc).__name__,
                    "retryable": category in {"rate_limit", "server_error", "timeout", "transport"},
                },
                "payload": response if isinstance(response, dict) else {},
            },
        )

    @staticmethod
    def _classify_error(provider_code: str) -> str:
        value = provider_code.lower()
        if "throttl" in value or "too_many_requests" in value:
            return "rate_limit"
        if "accessdenied" in value or "unrecognizedclient" in value:
            return "auth"
        if "validation" in value:
            return "bad_request"
        if "resource" in value and "notfound" in value:
            return "not_found"
        if "timeout" in value:
            return "timeout"
        if "internal" in value or "serviceunavailable" in value:
            return "server_error"
        return "unknown"

    @staticmethod
    def _has_boto3() -> bool:
        return importlib.util.find_spec("boto3") is not None

    @staticmethod
    def _client(*, region: str, profile: str, timeout: int):
        import boto3
        from botocore.config import Config

        session_kwargs: dict[str, str] = {}
        if profile:
            session_kwargs["profile_name"] = profile
        session = boto3.Session(**session_kwargs)
        config = Config(read_timeout=timeout, connect_timeout=min(timeout, 60))
        return session.client("bedrock-runtime", region_name=region, config=config)
