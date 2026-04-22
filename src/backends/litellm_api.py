"""LiteLLM gateway backend using the OpenAI-compatible Responses API."""

from __future__ import annotations

import os

from .openai_compatible_api import OpenAICompatibleResponsesApiBackend
from .types import BackendCapabilities


class LiteLLMApiBackend(OpenAICompatibleResponsesApiBackend):
    name = "litellm-api"
    api_key_env_vars = ("LITELLM_API_KEY", "OPENAI_API_KEY")
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="aggregator",
        supports_json_schema=True,
        supports_budget_cap=False,
        supports_rate_limit_detection=False,
        supports_system_prompt=True,
        supports_streaming=True,
        supports_response_format=True,
        supports_org_routing=False,
        supports_tools=False,
        default_model="openai/gpt-4.1-mini",
    )

    def default_service_base_url(self) -> str:
        return os.environ.get("LITELLM_BASE_URL", "") or "http://localhost:4000"
