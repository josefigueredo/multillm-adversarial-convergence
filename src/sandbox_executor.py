"""Sandbox executor for policy-bound tool-capable execution.

Provides :class:`SandboxExecutor` — the execution boundary that makes
``tool_execution_mode: sandboxed`` operationally real.

Design contract
---------------
- :class:`~src.security_runtime.RuntimeSecurityPolicy` stays **pure** and
  immutable.  No enforcement logic lives there.
- :class:`SandboxExecutor` owns all execution behavior: cwd, env shaping,
  write-boundary validation, and network-dispatch validation.
- :class:`~src.policy_denial.PolicyDeniedError` is the only denial signal.
- Construction has **no filesystem side effects**.  Call
  :meth:`SandboxExecutor.prepare_workspace` explicitly to create the workspace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .policy_denial import PolicyDeniedError

if TYPE_CHECKING:
    from .security_runtime import RuntimeSecurityPolicy


class SandboxExecutor:
    """Policy-bound execution boundary for tool-capable actions.

    Parameters
    ----------
    policy:
        The resolved, immutable runtime security policy for this run.
        Provides all enforcement questions (write roots, network mode, etc.).
    workspace_dir:
        The run-scoped workspace directory.  Typically
        ``output_dir / ".workspace"``.  This path is *declared* here but not
        created until :meth:`prepare_workspace` is called.
    """

    def __init__(self, policy: "RuntimeSecurityPolicy", workspace_dir: Path) -> None:
        self._policy = policy
        self._workspace_dir = workspace_dir

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
    # Workspace setup
    # ------------------------------------------------------------------

    def prepare_workspace(self) -> Path:
        """Create the workspace directory if it does not already exist.

        Safe to call multiple times (idempotent).

        Returns
        -------
        Path
            The workspace directory path.
        """
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        return self._workspace_dir

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
        """Raise PolicyDeniedError when *path* violates the filesystem boundary."""
        if self._policy.is_write_allowed(path):
            return
        roots = self._policy.allowed_write_roots()
        boundary = roots[0].name if roots else "none"
        raise PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action=action,
            requested_path=str(path),
            allowed_boundary=boundary,
        )

    def _check_network(self, action: str, destination_type: str) -> None:
        """Raise PolicyDeniedError when *destination_type* violates network policy."""
        if self._policy.is_network_allowed(destination_type=destination_type):
            return
        raise PolicyDeniedError(
            reason_code="network_access_disallowed",
            policy_field="sandbox.network_access",
            requested_action=action,
            allowed_boundary=self._policy.network_mode(),
        )
