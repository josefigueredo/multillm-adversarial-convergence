"""Abstract base class for sandbox execution backends.

A :class:`SandboxBackend` encapsulates the **substrate-specific** operations
needed to run sandboxed tool calls.  Concrete implementations differ on how
they create workspaces and shape execution environments:

- :class:`~src.sandbox.backends.local_process.LocalProcessBackend` — pure
  local subprocess isolation (workspace cwd + env allowlist)
- Future: container-backed backend (same interface, stronger isolation)

The backend owns two responsibilities:

1. **Workspace initialization** — creating (or provisioning) the execution
   workspace and returning its authoritative path.  A container backend might
   return a container-mount path rather than a host path.

2. **Environment shaping** — producing a sanitized subprocess environment
   dict.  The strategy (allowlist, injection, etc.) is substrate-specific.

Policy enforcement (write-boundary checks, network policy) is *not* a
backend responsibility.  That logic lives in
:class:`~src.sandbox_executor.SandboxExecutor`, which delegates only the
substrate mechanics here.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path


class SandboxBackend(ABC):
    """Abstract sandbox execution substrate.

    Implementors own workspace creation and environment shaping for their
    specific execution substrate.  Policy authorization (write/network rules)
    is handled by :class:`~src.sandbox_executor.SandboxExecutor`.
    """

    @abstractmethod
    def prepare_workspace(self) -> Path:
        """Initialize the execution workspace and return its authoritative path.

        For a local-process backend this is a simple ``mkdir``.  For a
        container backend it might start a container and return a mount path
        that differs from the host path.

        Must be idempotent — safe to call multiple times.

        Returns
        -------
        Path
            The authoritative execution workspace path for this backend.
            Callers should use the *returned* path as the cwd for subprocess
            execution, not any path passed to the backend at construction.
        """

    @abstractmethod
    def build_environment(
        self,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return a sanitized subprocess environment for sandboxed execution.

        Parameters
        ----------
        base_env:
            Source environment to filter or transform.  When ``None``, the
            backend uses the current process environment.  The source mapping
            is **never mutated**.

        Returns
        -------
        dict[str, str]
            A new dict suitable for passing as ``env`` to subprocess calls.
        """

    @abstractmethod
    def run_subprocess(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run *argv* in the sandbox substrate.

        Parameters
        ----------
        argv:
            Command and arguments as a list of strings.  Never a shell string.
        cwd:
            Working directory for the subprocess.  ``None`` → backend default.
        env:
            Explicit environment dict.  ``None`` → backend default (typically
            the result of :meth:`build_environment`).
        timeout:
            Seconds before the subprocess is killed.  ``None`` → no timeout.

        Returns
        -------
        tuple[int, str, str]
            ``(returncode, stdout, stderr)`` — both stdout and stderr are
            captured as strings.  This normalized shape is identical across
            all backend implementations.
        """
