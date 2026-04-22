"""Tests for HTTP transport behavior in ApiBackend."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

from src.backends.base_api import ApiBackend
from src.backends.types import AgentResponse, BackendCapabilities, CallOptions


class _ResponseStub:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _StreamResponseStub:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _StubApiBackend(ApiBackend):
    name = "stub-api-transport"
    api_key_env_vars = ("OPENAI_API_KEY",)
    capabilities = BackendCapabilities(
        transport="api",
        provider_kind="direct",
        supports_tools=False,
        default_model="gpt-test",
    )

    def build_request(self, prompt: str, opts: CallOptions) -> tuple[str, dict[str, str], dict[str, object]]:
        return (
            "https://api.example.com/v1/responses",
            {"Content-Type": "application/json"},
            {"model": opts.model or "gpt-test", "input": prompt},
        )

    def parse_payload(self, payload: dict[str, object]) -> AgentResponse:
        usage = payload.get("usage", {})
        return AgentResponse(
            text=str(payload.get("output_text", "")),
            cost_usd=0.0,
            is_error=False,
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            raw=payload,
        )


def test_post_json_uses_expected_url_headers_body_and_timeout():
    backend = _StubApiBackend()
    with patch("src.backends.base_api.urllib.request.urlopen", return_value=_ResponseStub({
        "output_text": "hi",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    })) as mock_urlopen:
        payload = backend._post_json("hello", CallOptions(model="gpt-test"), timeout=17)
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://api.example.com/v1/responses"
    assert request.headers["Content-type"] == "application/json"
    assert json.loads(request.data.decode("utf-8")) == {"model": "gpt-test", "input": "hello"}
    assert mock_urlopen.call_args.kwargs["timeout"] == 17
    assert payload["output_text"] == "hi"


def test_post_json_uses_default_timeout_when_non_positive_timeout():
    backend = _StubApiBackend()
    with patch("src.backends.base_api.urllib.request.urlopen", return_value=_ResponseStub({
        "output_text": "hi",
    })) as mock_urlopen:
        backend._post_json("hello", CallOptions(model="gpt-test"), timeout=0)
    assert mock_urlopen.call_args.kwargs["timeout"] == backend.default_timeout_seconds


def test_invoke_maps_http_429_to_rate_limit_error():
    backend = _StubApiBackend()
    error = urllib.error.HTTPError(
        url="https://api.example.com/v1/responses",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=BytesIO(b'{"error":{"type":"rate_limit_error","message":"Slow down"}}'),
    )
    with patch.object(backend, "_post_json", side_effect=error):
        resp = backend.invoke("hello", CallOptions(model="gpt-test"), timeout=17)
    assert resp.is_error is True
    assert resp.raw["error"]["category"] == "rate_limit"
    assert resp.raw["error"]["provider_code"] == "rate_limit_error"
    assert resp.raw["error"]["retryable"] is True


def test_invoke_maps_transport_error():
    backend = _StubApiBackend()
    with patch.object(backend, "_post_json", side_effect=urllib.error.URLError("network down")):
        resp = backend.invoke("hello", CallOptions(model="gpt-test"), timeout=17)
    assert resp.is_error is True
    assert resp.raw["error"]["category"] == "transport"
    assert resp.raw["error"]["retryable"] is True


def test_invoke_maps_malformed_json_error():
    backend = _StubApiBackend()
    with patch.object(backend, "_post_json", side_effect=json.JSONDecodeError("bad json", "x", 0)):
        resp = backend.invoke("hello", CallOptions(model="gpt-test"), timeout=17)
    assert resp.is_error is True
    assert resp.raw["error"]["category"] == "malformed_response"


def test_post_stream_yields_server_sent_event_payloads():
    backend = _StubApiBackend()
    stream = _StreamResponseStub([
        b"event: response.created\n",
        b'data: {"type":"response.created"}\n',
        b"\n",
        b"event: response.output_text.delta\n",
        b'data: {"type":"response.output_text.delta","delta":"Hi"}\n',
        b"\n",
        b"data: [DONE]\n",
        b"\n",
    ])
    with patch("src.backends.base_api.urllib.request.urlopen", return_value=stream):
        events = list(backend._post_stream("hello", CallOptions(model="gpt-test", stream=True), timeout=17))
    assert events == [
        {"type": "response.created"},
        {"type": "response.output_text.delta", "delta": "Hi"},
    ]
