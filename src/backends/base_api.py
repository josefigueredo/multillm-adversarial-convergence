"""Shared base class for HTTP API backends."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from abc import abstractmethod
from typing import Any

from .base import Backend
from .types import AgentResponse, CallOptions, PromptMode


class ApiBackend(Backend):
    """Base backend for direct HTTP API integrations."""

    _abstract_base = True
    api_key_env_vars: tuple[str, ...] = ()
    default_timeout_seconds: int = 300

    def cli_executable(self) -> str:
        return ""

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        return []

    def parse_response(self, stdout: str) -> AgentResponse:
        payload = json.loads(stdout)
        return self.parse_payload(payload)

    def check_available(self) -> bool:
        return bool(self._api_key())

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        try:
            payload = self._post_json(prompt, opts, timeout=timeout)
            return self.parse_payload(payload)
        except TimeoutError as exc:
            return self._error_response(
                category="timeout",
                message=str(exc) or "Request timed out",
                retryable=True,
                exception_type=type(exc).__name__,
            )
        except urllib.error.HTTPError as exc:
            details = self._extract_http_error_details(exc)
            return self._error_response(**details)
        except urllib.error.URLError as exc:
            return self._error_response(
                category="transport",
                message=str(getattr(exc, "reason", exc)) or "Transport error",
                retryable=True,
                exception_type=type(exc).__name__,
            )
        except json.JSONDecodeError as exc:
            return self._error_response(
                category="malformed_response",
                message=str(exc) or "Malformed JSON response",
                exception_type=type(exc).__name__,
            )

    @abstractmethod
    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Return ``(url, headers, body)`` for an API call."""

    @abstractmethod
    def parse_payload(self, payload: dict[str, Any]) -> AgentResponse:
        """Parse a JSON payload into an ``AgentResponse``."""

    def extract_error_details(self, payload: dict[str, Any] | None, status_code: int = 0) -> dict[str, Any]:
        """Normalize provider-specific error payloads into a common shape."""
        payload = payload if isinstance(payload, dict) else {}
        err = payload.get("error", payload)
        if not isinstance(err, dict):
            err = {}
        provider_code = str(
            err.get("type")
            or err.get("code")
            or payload.get("type")
            or payload.get("code")
            or ""
        )
        provider_status = str(err.get("status") or payload.get("status") or "")
        message = str(err.get("message") or payload.get("message") or "Request failed")
        category = self._classify_error(status_code, provider_code, provider_status)
        return {
            "category": category,
            "message": message,
            "status_code": status_code,
            "provider_code": provider_code,
            "provider_status": provider_status,
            "retryable": category in {"timeout", "transport", "rate_limit", "server_error"},
            "payload": payload,
        }

    def _api_key(self) -> str:
        for name in self.api_key_env_vars:
            value = os.environ.get(name, "")
            if value:
                return value
        return ""

    def _extract_http_error_details(self, exc: urllib.error.HTTPError) -> dict[str, Any]:
        body = self._decode_http_error_body(exc)
        payload: dict[str, Any] | None = None
        if body:
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None
        details = self.extract_error_details(payload, exc.code)
        if not payload and body:
            details["message"] = body
            details["payload"] = {"body": body}
        details["exception_type"] = type(exc).__name__
        return details

    def _post_json(self, prompt: str, opts: CallOptions, *, timeout: int) -> dict[str, Any]:
        url, headers, body = self.build_request(prompt, opts)
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        request_timeout = timeout if timeout > 0 else self.default_timeout_seconds
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_stream(self, prompt: str, opts: CallOptions, *, timeout: int):
        url, headers, body = self.build_request(prompt, opts)
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        request_timeout = timeout if timeout > 0 else self.default_timeout_seconds
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            for line in response:
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    continue
                yield json.loads(payload)

    def _base_url(self, default_url: str) -> str:
        provider = self.provider_config
        base_url = getattr(provider, "base_url", "") if provider is not None else ""
        if not base_url:
            return default_url
        parsed = urllib.parse.urlsplit(default_url)
        return f"{base_url.rstrip('/')}{parsed.path}"

    @staticmethod
    def _decode_http_error_body(exc: urllib.error.HTTPError) -> str:
        try:
            body = exc.read()
        except Exception:
            return ""
        if not body:
            return ""
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            return ""

    @staticmethod
    def _classify_error(status_code: int, provider_code: str = "", provider_status: str = "") -> str:
        value = f"{provider_code} {provider_status}".lower()
        if "quota" in value or "resource_exhausted" in value:
            return "quota"
        if "rate_limit" in value or "throttl" in value or "too_many_requests" in value:
            return "rate_limit"
        if "auth" in value or "unauthorized" in value or "invalid_api_key" in value:
            return "auth"
        if "permission" in value or "forbidden" in value:
            return "permission"
        if "not_found" in value:
            return "not_found"
        if "invalid" in value or "bad_request" in value or "request_too_large" in value:
            return "bad_request"
        if "overloaded" in value or "unavailable" in value or "api_error" in value or "internal" in value:
            return "server_error"
        if status_code == 401:
            return "auth"
        if status_code == 403:
            return "permission"
        if status_code == 404:
            return "not_found"
        if status_code == 408:
            return "timeout"
        if status_code == 429:
            return "rate_limit"
        if status_code in {400, 413, 422}:
            return "bad_request"
        if status_code >= 500:
            return "server_error"
        return "unknown"

    @staticmethod
    def _error_response(
        *,
        category: str,
        message: str,
        status_code: int = 0,
        provider_code: str = "",
        provider_status: str = "",
        retryable: bool = False,
        payload: dict[str, Any] | None = None,
        exception_type: str = "",
    ) -> AgentResponse:
        return AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=True,
            raw={
                "error": {
                    "category": category,
                    "message": message,
                    "status_code": status_code,
                    "provider_code": provider_code,
                    "provider_status": provider_status,
                    "retryable": retryable,
                    "exception_type": exception_type,
                },
                "payload": payload or {},
            },
        )

    @staticmethod
    def _append_query_params(url: str, params: dict[str, str]) -> str:
        encoded = urllib.parse.urlencode(params)
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{encoded}" if encoded else url
