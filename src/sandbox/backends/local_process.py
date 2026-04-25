"""Local-process sandbox backend.

Implements :class:`~src.sandbox.backends.base.SandboxBackend` using the
host filesystem and process environment.  Workspace creation is a plain
``mkdir``; environment shaping is an explicit allowlist filter.

This is **process-level isolation** — not container-grade security.  It
reduces ambient environment leakage and bounds the subprocess working
directory, but does not prevent a compromised subprocess from accessing host
resources outside the workspace.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from .base import SandboxBackend


# ---------------------------------------------------------------------------
# Env allowlist — explicit list of vars preserved in sandboxed subprocesses
# ---------------------------------------------------------------------------

#: Environment variable names kept by :meth:`LocalProcessBackend.build_environment`.
#: Matching is case-insensitive.
#:
#: Stripped (not included):
#: - ``SSH_AUTH_SOCK``, ``GPG_AGENT_INFO`` — agent sockets
#: - ``HISTFILE``, ``HISTSIZE``, ``HISTCONTROL`` — shell history
#: - ``CI``, ``GITHUB_ACTIONS``, ``GITHUB_RUN_ID``, ``GITHUB_WORKFLOW`` — CI markers
#: - ``XDG_*`` — user config dirs (reduces config-path leakage)
#: - Any variable not explicitly listed here
_LOCAL_PROCESS_ENV_ALLOWLIST: frozenset[str] = frozenset({
    # Process execution
    "PATH",
    "PATHEXT",           # Windows: executable extensions
    "COMSPEC",           # Windows: command processor
    "SHELL",             # Unix: default shell

    # User identity (best-effort; may match host identity at this milestone)
    "HOME",
    "USERPROFILE",       # Windows equivalent of HOME
    "HOMEDRIVE",
    "HOMEPATH",
    "USER",
    "USERNAME",
    "LOGNAME",

    # Temporary directories (best-effort; not workspace-scoped at this milestone)
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


class LocalProcessBackend(SandboxBackend):
    """Subprocess-based sandbox backend using host filesystem and env allowlist.

    Parameters
    ----------
    workspace_dir:
        The host filesystem path to use as the execution workspace.
        :meth:`prepare_workspace` creates this directory.
    """

    def __init__(self, workspace_dir: Path) -> None:
        self._workspace_dir = workspace_dir

    def prepare_workspace(self) -> Path:
        """Create the workspace directory and return its path.

        Idempotent — safe to call multiple times even if the directory
        already exists.

        Returns
        -------
        Path
            The workspace directory path (same as the path provided at
            construction).
        """
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        return self._workspace_dir

    def build_environment(
        self,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Filter *base_env* through the local-process env allowlist.

        Keeps only variables explicitly listed in
        :data:`_LOCAL_PROCESS_ENV_ALLOWLIST`.  Matching is case-insensitive.
        The source mapping is never mutated.

        Parameters
        ----------
        base_env:
            Source environment.  ``None`` → :data:`os.environ`.

        Returns
        -------
        dict[str, str]
            A new dict containing only the allowlisted keys present in
            *base_env*.
        """
        source: Mapping[str, str] = base_env if base_env is not None else os.environ
        allow_upper = {k.upper() for k in _LOCAL_PROCESS_ENV_ALLOWLIST}
        return {k: v for k, v in source.items() if k.upper() in allow_upper}
