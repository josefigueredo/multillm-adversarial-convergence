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

Environment shaping
-------------------
:meth:`SandboxExecutor.build_environment` produces a sanitized environment
mapping for sandboxed subprocess execution.  It filters an input environment
through :data:`_SANDBOX_ENV_ALLOWLIST`, preserving only keys that are both
recognised as safe and necessary for backend subprocess execution.

This is **process-level isolation** — not container-grade security.  The
workspace cwd and write-boundary enforcement are the primary execution
boundary; env shaping reduces ambient environment leakage.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .policy_denial import PolicyDeniedError

if TYPE_CHECKING:
    from .security_runtime import RuntimeSecurityPolicy


# ---------------------------------------------------------------------------
# Sandbox environment allowlist
# ---------------------------------------------------------------------------

#: Explicit allowlist of environment variable names preserved by
#: :meth:`SandboxExecutor.build_environment`.  Matching is case-insensitive
#: so that Windows uppercase keys and Unix lowercase variants both survive.
#:
#: Notably **not** included (stripped from sandboxed subprocess env):
#:
#: - ``SSH_AUTH_SOCK``, ``GPG_AGENT_INFO`` — agent sockets
#: - ``HISTFILE``, ``HISTSIZE``, ``HISTCONTROL`` — shell history
#: - ``CI``, ``GITHUB_ACTIONS``, ``GITHUB_RUN_ID``, ``GITHUB_WORKFLOW`` — CI markers
#: - ``XDG_*`` — user config dirs (stripped to reduce config-path leakage)
#: - Any variable not explicitly listed here
_SANDBOX_ENV_ALLOWLIST: frozenset[str] = frozenset({
    # Process execution
    "PATH",
    "PATHEXT",           # Windows: executable extensions
    "COMSPEC",           # Windows: command processor
    "SHELL",             # Unix: default shell

    # User identity (best-effort; may match host identity in this milestone)
    "HOME",
    "USERPROFILE",       # Windows equivalent of HOME
    "HOMEDRIVE",
    "HOMEPATH",
    "USER",
    "USERNAME",
    "LOGNAME",

    # Temporary directories (best-effort; not workspace-scoped in this milestone)
    "TMPDIR",
    "TMP",
    "TEMP",

    # Locale / encoding
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TERM",

    # Display / colour
    "NO_COLOR",
    "FORCE_COLOR",

    # Network / TLS (required for backend API calls through the subprocess)
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",

    # Backend API credentials (preserved so subprocesses can call their APIs)
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "COPILOT_TOKEN",

    # Windows system directories and CPU info
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "NUMBER_OF_PROCESSORS",
    "OS",
    "PROCESSOR_ARCHITECTURE",
    "PROCESSOR_IDENTIFIER",
    "PROCESSOR_LEVEL",
    "PROCESSOR_REVISION",
})


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
    # Environment shaping
    # ------------------------------------------------------------------

    def build_environment(
        self,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return a sanitized environment dict for sandboxed subprocess execution.

        Filters *base_env* through :data:`_SANDBOX_ENV_ALLOWLIST`, keeping only
        keys on the explicit allowlist.  Matching is case-insensitive so that
        Windows uppercase variable names and Unix lowercase variants both survive
        filtering correctly.

        This is **process-level isolation only** — not container-grade security.
        The primary execution boundary is the workspace cwd plus write-boundary
        enforcement.  This method reduces ambient environment leakage without
        claiming stronger guarantees.

        Notable omissions (stripped):
        ``SSH_AUTH_SOCK``, ``GPG_AGENT_INFO``, ``HISTFILE``, ``CI``,
        ``GITHUB_ACTIONS``, ``XDG_*``, and any variable not explicitly
        on :data:`_SANDBOX_ENV_ALLOWLIST`.

        Parameters
        ----------
        base_env:
            Source environment to filter.  When ``None``, :data:`os.environ`
            is used.  The source mapping is **never mutated**.

        Returns
        -------
        dict[str, str]
            A new dict containing only the allowlisted keys present in
            *base_env*.
        """
        source: Mapping[str, str] = base_env if base_env is not None else os.environ
        allow_upper = {k.upper() for k in _SANDBOX_ENV_ALLOWLIST}
        return {k: v for k, v in source.items() if k.upper() in allow_upper}

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
        raise PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action=action,
            requested_path=str(path),
            allowed_boundary=self._policy.filesystem_access,
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
