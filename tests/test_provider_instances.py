"""Tests for provider-instance instantiation helpers."""

from src.provider_instances import backend_label, instantiate_provider_backends
from src.config import BackendsConfig, ProviderConfig


def test_instantiate_provider_backends_uses_instance_names():
    providers = {
        "primary_reasoner": ProviderConfig(adapter="claude-cli", model="opus"),
        "fast_research": ProviderConfig(adapter="codex-cli", model="gpt-5.4"),
    }
    roles = BackendsConfig(
        primary="primary_reasoner",
        research=("primary_reasoner", "fast_research"),
    )

    backends = instantiate_provider_backends(providers, roles)

    assert set(backends) == {"primary_reasoner", "fast_research"}
    assert backends["primary_reasoner"].name == "claude-cli"
    assert backends["primary_reasoner"].instance_name == "primary_reasoner"
    assert backends["primary_reasoner"].provider_config == providers["primary_reasoner"]
    assert backend_label(backends["fast_research"]) == "fast_research"
