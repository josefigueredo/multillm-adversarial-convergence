"""Provider-instance instantiation helpers."""

from __future__ import annotations

from .backends import Backend, get_backend
from .config import BackendsConfig, ProviderConfig


def instantiate_provider_backends(
    providers: dict[str, ProviderConfig],
    role_config: BackendsConfig,
) -> dict[str, Backend]:
    """Instantiate backends keyed by provider instance name.

    The ``provider_config`` and ``instance_name`` fields are declared on
    ``Backend`` so the assignment here is normal attribute storage, not
    monkey-patching — type checkers and IDEs can see the contract.
    """
    instances: dict[str, Backend] = {}
    for instance_name in role_config.all_backend_names():
        provider = providers[instance_name]
        backend = get_backend(provider.adapter)
        backend.instance_name = instance_name
        backend.provider_config = provider
        instances[instance_name] = backend
    return instances


def backend_label(backend: Backend) -> str:
    """Return the configured provider instance name when present.

    The isinstance check guards against MagicMock-based tests where
    ``backend.instance_name`` auto-creates a non-string mock.
    """
    label = backend.instance_name
    return label if isinstance(label, str) and label else backend.name
