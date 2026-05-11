"""Shared base for direct OpenAI Responses API integrations."""

from __future__ import annotations

from .openai_compatible_api import OpenAICompatibleResponsesApiBackend
from .types import CallOptions


class OpenAIDirectResponsesApiBackend(OpenAICompatibleResponsesApiBackend):
    """Base class for direct OpenAI Responses API backends."""

    _abstract_base = True

    def default_service_base_url(self) -> str:
        return "https://api.openai.com"

    def check_available(self) -> bool:
        return bool(self._api_key())

    def build_request(self, prompt: str, opts: CallOptions):
        url, headers, body = super().build_request(prompt, opts)
        headers["Authorization"] = f"Bearer {self._api_key()}"
        return url, headers, body
