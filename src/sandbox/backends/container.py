"""Container-backed sandbox backend — MM13 Step 1.

Implements :class:`~src.sandbox.backends.base.SandboxBackend` using a
container runtime (Docker-compatible CLI) as the execution substrate.

This backend is **optional**: the module imports cleanly even when Docker is
not installed.  Call :meth:`ContainerBackend.is_available` before constructing
an instance to determine whether a compatible container runtime is present.

Design contract
---------------
- ``prepare_workspace()`` creates the *host-side* workspace directory and
  returns its path.  The host directory is bind-mounted into the container
  at :attr:`container_workspace` when a container is actually started (wired
  in later steps).
- ``build_environment()`` returns a minimal allowlist-filtered environment
  suitable for injection into a container process.  Secret-bearing variables
  (API keys, tokens, credentials) are never forwarded.
- ``is_available()`` checks whether a Docker-compatible CLI is on ``$PATH``
  using :func:`shutil.which`.  No network or daemon contact is made.
"""

from __future__ import annotations

import os
import subprocess
import shutil
from collections.abc import Mapping
from pathlib import Path

from .base import SandboxBackend

# Variables allowed into a container environment.  This is intentionally more
# conservative than LocalProcessBackend's allowlist: containers should start
# with a clean, minimal environment.
_CONTAINER_ALLOWED_ENV: frozenset[str] = frozenset({
    "PATH",
    "HOME",
    "USER",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "TZ",
})

# Substrings that, if found in an env var name (case-insensitive), cause it to
# be stripped even if it appears in the allowlist.  Guards against leaking
# secrets via renamed variables.
_SECRET_SUBSTRINGS: tuple[str, ...] = (
    "SECRET",
    "API_KEY",
    "TOKEN",
    "PASSWORD",
    "CREDENTIAL",
    "PRIVATE_KEY",
)


def _is_secret(name: str) -> bool:
    upper = name.upper()
    return any(s in upper for s in _SECRET_SUBSTRINGS)


class ContainerBackend(SandboxBackend):
    """Container-backed sandbox execution substrate.

    Delegates workspace creation to a host-side directory that is intended to
    be bind-mounted into a container.  Environment shaping applies a strict
    allowlist and strips any variable whose name contains a secret-bearing
    substring.

    Parameters
    ----------
    image:
        OCI image reference to use for the container (e.g.
        ``"python:3.11-slim"``).
    host_workspace:
        Host filesystem path for the execution workspace directory.
        :meth:`prepare_workspace` creates this directory.
    container_workspace:
        Absolute path *inside* the container where *host_workspace* will be
        bind-mounted.  Defaults to ``"/sandbox/workspace"``.
    """

    _DEFAULT_CONTAINER_WORKSPACE: str = "/sandbox/workspace"

    def __init__(
        self,
        image: str,
        host_workspace: Path,
        container_workspace: str | None = None,
    ) -> None:
        _cw = (
            container_workspace
            if container_workspace is not None
            else self._DEFAULT_CONTAINER_WORKSPACE
        )
        if not _cw.startswith("/"):
            raise ValueError(
                f"container_workspace must be an absolute path; got {_cw!r}"
            )
        self._image = image
        self._host_workspace = host_workspace
        self._container_workspace = _cw

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def image(self) -> str:
        """OCI image reference for the container."""
        return self._image

    @property
    def host_workspace(self) -> Path:
        """Host-side workspace directory path."""
        return self._host_workspace

    @property
    def container_workspace(self) -> str:
        """Absolute path inside the container for the workspace mount."""
        return self._container_workspace

    # ── SandboxBackend interface ──────────────────────────────────────────────

    def prepare_workspace(self) -> Path:
        """Create the host workspace directory and return the authoritative container execution path.

        The host directory is provisioned so it can be bind-mounted into the
        container.  The *returned path* is the container-side mount point — the
        path callers should use as the cwd for subprocess execution inside the
        container.

        Idempotent — safe to call multiple times.

        Returns
        -------
        Path
            The authoritative execution workspace path inside the container
            (i.e. ``Path(self.container_workspace)``), not the host-side path.
        """
        self._host_workspace.mkdir(parents=True, exist_ok=True)
        return Path(self._container_workspace)

    def build_environment(
        self,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return a minimal allowlisted environment for container execution.

        Applies a strict allowlist and then strips any remaining variable whose
        name contains a secret-bearing substring.  The source mapping is never
        mutated.

        Parameters
        ----------
        base_env:
            Source environment.  ``None`` → :data:`os.environ`.

        Returns
        -------
        dict[str, str]
            A new dict containing only safe, non-secret variables.
        """
        source: Mapping[str, str] = base_env if base_env is not None else os.environ
        result: dict[str, str] = {}
        for k, v in source.items():
            if k.upper() in _CONTAINER_ALLOWED_ENV and not _is_secret(k):
                result[k] = v
        return result

    # ── Availability check ────────────────────────────────────────────────────

    @classmethod
    def is_available(cls) -> bool:
        """Return ``True`` if a Docker-compatible CLI is available on ``$PATH``.

        Uses :func:`shutil.which` — no daemon or network contact is made.
        Safe to call without Docker installed.
        """
        return shutil.which("docker") is not None

    # ── SandboxBackend: run_subprocess ────────────────────────────────────────

    def run_subprocess(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run *argv* inside a Docker container.

        Builds a ``docker run`` invocation (no shell, no string interpolation)
        that bind-mounts the host workspace at the container workspace path,
        forwards the supplied environment variables, and executes *argv* inside
        the specified image.

        Parameters
        ----------
        argv:
            Command and arguments to run inside the container.
        cwd:
            Unused for the container path (the container cwd is the mounted
            workspace); accepted for interface parity with other backends.
        env:
            Environment variables to inject.  Each key becomes a
            ``--env KEY=VALUE`` flag.  ``None`` → no extra env flags.
        timeout:
            Seconds before the subprocess is killed.  ``None`` → no timeout.

        Returns
        -------
        tuple[int, str, str]
            ``(returncode, stdout, stderr)`` from the docker run invocation.
        """
        docker_argv: list[str] = [
            "docker", "run", "--rm",
            "--mount", (
                f"type=bind"
                f",source={self._host_workspace}"
                f",target={self._container_workspace}"
                f",readonly=false"
            ),
            "--workdir", str(cwd) if cwd is not None else self._container_workspace,
        ]
        for key, value in (env or {}).items():
            docker_argv += ["--env", f"{key}={value}"]
        docker_argv += [self._image, *argv]

        result = subprocess.run(
            docker_argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.returncode, result.stdout, result.stderr)
