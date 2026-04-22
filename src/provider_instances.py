"""Provider-instance instantiation helpers."""

from __future__ import annotations

from typing import Any

from .backends import Backend, get_backend
from .config import BackendsConfig, ProviderConfig


def instantiate_provider_backends(
    providers: dict[str, ProviderConfig],
    role_config: BackendsConfig,
) -> dict[str, Backend]:
    """Instantiate backends keyed by provider instance name."""
    instances: dict[str, Backend] = {}
    for instance_name in role_config.all_backend_names():
        provider = providers[instance_name]
        backend = get_backend(provider.adapter)
        setattr(backend, "instance_name", instance_name)
        setattr(backend, "provider_config", provider)
        instances[instance_name] = backend
    return instances


def backend_label(backend: Backend) -> str:
    """Return the configured provider instance name when present."""
    label = getattr(backend, "instance_name", None)
    return label if isinstance(label, str) and label else backend.name
