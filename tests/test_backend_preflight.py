"""Tests for live backend preflight probes."""

from __future__ import annotations

import pytest

from src.backend_preflight import preflight_backends, require_preflight_success
from src.backends.types import AgentResponse, BackendCapabilities, CallOptions
from src.config import BackendsConfig, ExecutionConfig, ProviderConfig


class FakeBackend:
    name = "fake-cli"

    def __init__(self, response: AgentResponse, *, transport: str = "cli", default_model: str = "fake-model"):
        self.response = response
        self.calls: list[tuple[str, CallOptions, int]] = []
        self.capabilities = BackendCapabilities(transport=transport, default_model=default_model)

    def invoke(self, prompt: str, opts: CallOptions, timeout: int = 300) -> AgentResponse:
        self.calls.append((prompt, opts, timeout))
        return self.response


def test_preflight_cli_backend_accepts_exact_ok():
    backend = FakeBackend(AgentResponse(text="OK", cost_usd=0.0, is_error=False))
    execution = ExecutionConfig(backend_preflight_timeout_seconds=12)

    results = preflight_backends(backends={"main": backend}, execution=execution)

    assert results[0].ok is True
    assert backend.calls[0][1].max_turns == 1
    assert backend.calls[0][1].allowed_tools == ""
    assert backend.calls[0][2] == 12


@pytest.mark.parametrize("text", ["OK.", '"OK"', " ok! ", "“OK.”"])
def test_preflight_cli_backend_accepts_harmless_ok_formatting(text):
    backend = FakeBackend(AgentResponse(text=text, cost_usd=0.0, is_error=False))

    results = preflight_backends(backends={"main": backend}, execution=ExecutionConfig())

    assert results[0].ok is True


@pytest.mark.parametrize("text", ["OK but quota is low", "OK\nYou're out of extra usage", "NOT OK"])
def test_preflight_cli_backend_rejects_non_exact_ok_text(text):
    backend = FakeBackend(AgentResponse(text=text, cost_usd=0.0, is_error=False))

    results = preflight_backends(backends={"main": backend}, execution=ExecutionConfig())

    assert results[0].ok is False


def test_preflight_cli_backend_rejects_quota_banner():
    backend = FakeBackend(
        AgentResponse(text="You're out of extra usage - resets later", cost_usd=0.0, is_error=False)
    )
    results = preflight_backends(backends={"main": backend}, execution=ExecutionConfig())

    assert results[0].ok is False
    with pytest.raises(RuntimeError, match="Backend preflight failed"):
        require_preflight_success(results)


def test_preflight_cli_backend_rejects_error_response():
    backend = FakeBackend(AgentResponse(text="", cost_usd=0.0, is_error=True))
    results = preflight_backends(backends={"main": backend}, execution=ExecutionConfig())

    assert results[0].ok is False
    assert results[0].reason == "backend returned an error"


def test_preflight_skips_api_backends():
    backend = FakeBackend(
        AgentResponse(text="", cost_usd=0.0, is_error=True),
        transport="api",
    )
    results = preflight_backends(backends={"api": backend}, execution=ExecutionConfig())

    assert results[0].skipped is True
    assert results[0].ok is True
    assert backend.calls == []


def test_preflight_probes_duplicate_backend_object_once():
    backend = FakeBackend(AgentResponse(text="OK", cost_usd=0.0, is_error=False))
    results = preflight_backends(
        backends={"primary": backend, "judge": backend},
        execution=ExecutionConfig(),
        backend_names=["primary", "judge"],
    )

    assert len(results) == 1
    assert len(backend.calls) == 1


def test_preflight_uses_provider_model_and_resolves_claude_shortname_for_non_claude():
    backend = FakeBackend(AgentResponse(text="OK", cost_usd=0.0, is_error=False), default_model="gpt-test")
    provider = ProviderConfig(adapter="fake-cli", model="opus")
    setattr(backend, "provider_config", provider)

    results = preflight_backends(
        backends={"critic": backend},
        execution=ExecutionConfig(backends=BackendsConfig(primary="critic")),
        provider_lookup={"critic": provider},
    )

    assert results[0].model == "gpt-test"
    assert backend.calls[0][1].model == "gpt-test"
