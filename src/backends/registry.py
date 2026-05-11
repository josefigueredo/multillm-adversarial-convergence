"""Backend registry — discovery and instantiation by name."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Backend

_REGISTRY: dict[str, type[Backend]] = {}


def _register(name: str, cls: type[Backend]) -> None:
    """Called by ``Backend.__init_subclass__`` to auto-register backends.

    Raises ``ValueError`` if *name* is empty, or if it collides with an
    already-registered class that isn't *cls*. Idempotent re-registration
    of the same class (e.g. when an aliased entry already points to it)
    is allowed.
    """
    if not name:
        raise ValueError(
            f"Cannot register backend {cls.__name__!r} with empty name; "
            "set a non-empty ``name`` class attribute."
        )
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"Backend name {name!r} is already registered to "
            f"{existing.__name__!r}; cannot reassign to {cls.__name__!r}."
        )
    _REGISTRY[name] = cls


def valid_backends() -> tuple[str, ...]:
    """Return all registered backend names (derived from the registry)."""
    return tuple(sorted(_REGISTRY))


def get_backend(name: str) -> Backend:
    """Instantiate a backend by name.

    Raises:
        ValueError: If the name is not recognised.
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown backend '{name}'. Must be one of: {', '.join(valid_backends())}"
        )
    return cls()


def get_backends(backend_names: set[str]) -> dict[str, Backend]:
    """Instantiate a set of backends by name, deduplicating instances."""
    return {name: get_backend(name) for name in backend_names}


def canonical_backend_name(name: str) -> str:
    """Return the canonical backend class name for a registered name or alias."""
    backend = get_backend(name)
    return backend.name
