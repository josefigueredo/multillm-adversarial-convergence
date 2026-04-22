"""Amazon Bedrock Converse adapter."""

from __future__ import annotations

import importlib.util
import json
import os
from typing import Any

from .base import Backend
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode, StreamEvent, ToolCallRequest


class BedrockApiBackend(Backend):
    name = "bedrock-api"
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="aggregator",
        supports_json_schema=False,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_streaming=True,
        supports_function_tools=True,
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
            if opts.tools:
                request["toolConfig"] = {
                    "tools": [
                        {
                            "toolSpec": {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": {"json": tool.input_schema},
                            }
                        }
                        for tool in opts.tools
                    ]
                }
                if opts.tool_choice == "required" and opts.tools:
                    request["toolConfig"]["toolChoice"] = {"tool": {"name": opts.tools[0].name}}
            payload = client.converse(**request)
            return self.parse_payload(payload)
        except Exception as exc:
            return self._error_response_from_exception(exc)

    def extract_function_tool_calls(self, payload: dict[str, Any]) -> list[ToolCallRequest]:
        calls: list[ToolCallRequest] = []
        output = payload.get("output", {})
        message = output.get("message", {}) if isinstance(output, dict) else {}
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            tool_use = block.get("toolUse")
            if not isinstance(tool_use, dict):
                continue
            calls.append(
                ToolCallRequest(
                    id=str(tool_use.get("toolUseId", "")),
                    call_id=str(tool_use.get("toolUseId", "")),
                    name=str(tool_use.get("name", "")),
                    arguments_json=json.dumps(tool_use.get("input", {})),
                    raw=block,
                )
            )
        return calls

    def build_tool_followup_input(
        self,
        prompt: str,
        response_payload: dict[str, Any],
        tool_outputs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        messages = list(response_payload.get("messages", []))
        if not messages:
            messages = [{"role": "user", "content": [{"text": prompt}]}]
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": item["call_id"],
                            "content": [{"text": item["output"]}],
                        }
                    }
                    for item in tool_outputs
                ],
            }
        )
        return messages

    def invoke_stream(self, prompt: str, opts: CallOptions, timeout: int = 300):
        model = opts.model or self.capabilities.default_model
        if not model:
            yield StreamEvent(type="error", raw={"error": {"message": "Missing model"}})
            return
        try:
            client = self._client(region=self._region(), profile=self._aws_profile(), timeout=timeout)
            request: dict[str, Any] = {
                "modelId": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
            }
            if opts.system_prompt:
                request["system"] = [{"text": opts.system_prompt}]

            response = client.converse_stream(**request)
            text_parts: list[str] = []
            usage: dict[str, Any] = {}

            for event in response.get("stream", []):
                if "messageStart" in event:
                    yield StreamEvent(type="start", raw=event)
                    continue
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    text = str(delta.get("text", "") or "")
                    if text:
                        text_parts.append(text)
                        yield StreamEvent(type="text_delta", text=text, raw=event)
                    continue
                if "metadata" in event:
                    metadata = event["metadata"]
                    if isinstance(metadata, dict) and isinstance(metadata.get("usage"), dict):
                        usage = metadata["usage"]
                    continue
                if any(key.endswith("Exception") for key in event):
                    yield StreamEvent(type="error", raw=event)
                    return
                if "messageStop" in event:
                    yield StreamEvent(
                        type="completed",
                        raw={
                            "response": {
                                "output": {"message": {"content": [{"text": "".join(text_parts)}]}},
                                "usage": usage,
                            }
                        },
                    )
                    return
        except Exception as exc:
            yield StreamEvent(type="error", raw=self._error_response_from_exception(exc).raw)

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
