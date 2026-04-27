"""Sandbox executor for policy-bound tool-capable execution.

Provides :class:`SandboxExecutor` — the execution boundary that makes
``tool_execution_mode: sandboxed`` operationally real.

Design contract
---------------
- :class:`~src.security_runtime.RuntimeSecurityPolicy` stays **pure** and
  immutable.  No enforcement logic lives there.
- :class:`SandboxExecutor` owns policy authorization: write-boundary
  validation, network-dispatch validation, and routing to the backend.
- :class:`~src.sandbox.backends.base.SandboxBackend` owns substrate
  mechanics: workspace creation and environment shaping.  Swapping the
  backend (e.g. container vs local-process) does not change the policy
  contract.
- :class:`~src.policy_denial.PolicyDeniedError` is the only denial signal.
- Construction has **no filesystem side effects**.  Call
  :meth:`SandboxExecutor.prepare_workspace` explicitly to create the
  workspace.

Environment shaping
-------------------
:meth:`SandboxExecutor.build_environment` delegates to the active backend.
The default backend (:class:`~src.sandbox.backends.local_process.LocalProcessBackend`)
applies an explicit allowlist filter — **process-level isolation** only, not
container-grade security.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .policy_denial import PolicyDeniedError
from .sandbox.backends import LocalProcessBackend, SandboxBackend

if TYPE_CHECKING:
    from collections.abc import Mapping
    from .security_runtime import RuntimeSecurityPolicy


#: Valid destination_type values for dispatch-level network checks.
_KNOWN_DISPATCH_DESTINATION_TYPES: frozenset[str] = frozenset({"web", "other"})


class SandboxExecutor:
    """Policy-bound execution boundary for tool-capable actions.

    :class:`SandboxExecutor` enforces policy rules (write boundaries, network
    access) and delegates substrate mechanics (workspace creation, environment
    shaping) to a :class:`~src.sandbox.backends.base.SandboxBackend`.

    Parameters
    ----------
    policy:
        The resolved, immutable runtime security policy for this run.
    workspace_dir:
        Declared workspace path.  Used to construct the default
        :class:`~src.sandbox.backends.local_process.LocalProcessBackend`
        when no *backend* is provided.  After :meth:`prepare_workspace`
        is called, :attr:`workspace_dir` reflects the authoritative path
        returned by the backend.
    backend:
        Explicit sandbox backend.  When ``None``, defaults to
        :class:`~src.sandbox.backends.local_process.LocalProcessBackend`
        initialized with *workspace_dir*.
    """

    def __init__(
        self,
        policy: "RuntimeSecurityPolicy",
        workspace_dir: Path,
        *,
        backend: SandboxBackend | None = None,
    ) -> None:
        self._policy = policy
        self._workspace_dir = workspace_dir
        self._backend: SandboxBackend = backend if backend is not None else LocalProcessBackend(workspace_dir)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def policy(self) -> "RuntimeSecurityPolicy":
        """The resolved runtime security policy for this executor."""
        return self._policy

    @property
    def workspace_dir(self) -> Path:
        """The run-scoped workspace directory (execution root)."""
        return self._workspace_dir

    def allowed_write_roots(self) -> list[Path]:
        """Return the list of permitted write roots from the active policy."""
        return self._policy.allowed_write_roots()

    def network_mode(self) -> str:
        """Return the resolved network access token (``unrestricted`` / ``web_only`` / ``none``)."""
        return self._policy.network_mode()

    # ------------------------------------------------------------------
    # Environment shaping
    # ------------------------------------------------------------------

    def build_environment(
        self,
        base_env: "Mapping[str, str] | None" = None,
    ) -> dict[str, str]:
        """Return a sanitized environment dict for sandboxed subprocess execution.

        Delegates to the active backend's :meth:`~SandboxBackend.build_environment`.
        The default backend applies an explicit allowlist filter (process-level
        isolation; not container-grade security).

        Parameters
        ----------
        base_env:
            Source environment to filter.  ``None`` → backend default
            (typically :data:`os.environ`).

        Returns
        -------
        dict[str, str]
            A new sanitized dict suitable for passing as ``env`` to subprocesses.
        """
        return self._backend.build_environment(base_env)

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def prepare_workspace(self, *, iteration: int | None = None) -> Path:
        """Initialize the execution workspace via the active backend.

        Delegates to :meth:`~SandboxBackend.prepare_workspace` and updates
        :attr:`workspace_dir` to the authoritative path returned by the backend.
        This allows container backends to return a different execution path
        (e.g. a container mount) without changing the executor's external API.

        When *iteration* is provided, the backend creates a per-iteration
        subdirectory and :attr:`workspace_dir` is updated to that path.

        Idempotent — safe to call multiple times.

        Parameters
        ----------
        iteration:
            Iteration number.  ``None`` → existing run-scoped behavior.
            Positive int → create and activate ``iter_<NNNN>/`` subdir.

        Returns
        -------
        Path
            The authoritative execution workspace path.
        """
        path = self._backend.prepare_workspace(iteration=iteration)
        self._workspace_dir = path
        return path

    # ------------------------------------------------------------------
    # Subprocess execution
    # ------------------------------------------------------------------

    def run_subprocess(
        self,
        argv: list[str],
        *,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run *argv* inside the active sandbox substrate.

        Builds the execution environment via the backend's
        :meth:`~SandboxBackend.build_environment`, then delegates to
        :meth:`~SandboxBackend.run_subprocess` with the executor's authoritative
        workspace as the working directory.

        Parameters
        ----------
        argv:
            Command and arguments.  Never passed through a shell.
        timeout:
            Seconds before the subprocess is killed.  ``None`` → no timeout.

        Returns
        -------
        tuple[int, str, str]
            ``(returncode, stdout, stderr)`` from the backend.
        """
        env = self._backend.build_environment()
        return self._backend.run_subprocess(
            argv,
            cwd=self._workspace_dir,
            env=env,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_tool_request(
        self,
        action: str,
        *,
        write_path: Optional[Path] = None,
        destination_type: Optional[str] = None,
    ) -> None:
        """Validate a tool request against the active runtime policy.

        Raises :class:`~src.policy_denial.PolicyDeniedError` if the request
        violates any active policy constraint.  Filesystem checks run before
        network checks.

        Parameters
        ----------
        action:
            Short label for the requested action (used in denial messages and
            audit events).
        write_path:
            Filesystem path the action intends to write to, or ``None`` when
            the action involves no filesystem write.
        destination_type:
            Network destination category — ``"web"`` for HTTP/HTTPS,
            ``"other"`` for anything else.  ``None`` means the action has no
            network component and network policy is not checked.
        """
        if write_path is not None:
            self._check_write(action, write_path)
        if destination_type is not None:
            self._check_network(action, destination_type)

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_write(self, action: str, path: Path) -> None:
        """Raise PolicyDeniedError when *path* violates the filesystem boundary.

        Checks the runtime policy first.  For container backends the executor's
        ``workspace_dir`` is updated to the container-side path by
        :meth:`prepare_workspace`; that path may differ from the policy's
        host-side workspace, so we also accept writes within the executor's
        own authoritative workspace path.
        """
        if self._policy.is_write_allowed(path):
            return
        # Also accept writes within the executor's own workspace_dir.
        # This handles container backends where _workspace_dir is a container-
        # side path that the host-scoped policy does not know about.
        if self._is_within_executor_workspace(path):
            return
        raise PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action=action,
            requested_path=str(path),
            allowed_boundary=self._policy.filesystem_access,
        )

    def _is_within_executor_workspace(self, path: Path) -> bool:
        """Return True when *path* falls within the executor's workspace_dir."""
        try:
            path.resolve().relative_to(self._workspace_dir.resolve())
            return True
        except ValueError:
            return False

    def _check_network(self, action: str, destination_type: str) -> None:
        """Raise PolicyDeniedError when *destination_type* violates network policy.

        Validates that *destination_type* is a recognised value before evaluating
        the network policy.  Unknown values fail immediately with
        ``reason_code="invalid_destination_type"`` regardless of the active network
        policy — this prevents misuse of the dispatch API from silently bypassing
        or mis-categorising network enforcement.
        """
        if destination_type not in _KNOWN_DISPATCH_DESTINATION_TYPES:
            raise PolicyDeniedError(
                reason_code="invalid_destination_type",
                policy_field="sandbox.network_access",
                requested_action=action,
            )
        if self._policy.is_network_allowed(destination_type=destination_type):
            return
        raise PolicyDeniedError(
            reason_code="network_access_disallowed",
            policy_field="sandbox.network_access",
            requested_action=action,
            allowed_boundary=self._policy.network_mode(),
        )
