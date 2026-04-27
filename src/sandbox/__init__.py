"""Sandbox subsystem — backend seam for execution substrate extensibility."""

from .backends.container import ContainerBackend
from .backends.local_process import LocalProcessBackend

__all__ = ["ContainerBackend", "LocalProcessBackend"]
