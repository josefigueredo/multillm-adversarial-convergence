"""OpenAI Responses API backend for Codex-style use."""

from __future__ import annotations

from .openai_direct_api import OpenAIDirectResponsesApiBackend
from .types import BackendCapabilities


class CodexApiBackend(OpenAIDirectResponsesApiBackend):
    name = "codex-api"
    api_key_env_vars = ("OPENAI_API_KEY",)
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_json_schema=True,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_streaming=True,
        supports_response_format=True,
        supports_org_routing=False,
        supports_tools=False,
        default_model="gpt-5.4",
    )
