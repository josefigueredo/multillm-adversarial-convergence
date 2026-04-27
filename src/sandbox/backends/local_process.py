"""Local-process sandbox backend.

Implements :class:`~src.sandbox.backends.base.SandboxBackend` using the
host filesystem and process environment.  Workspace creation is a plain
``mkdir``; environment shaping is driven by an explicit
:class:`SandboxEnvPolicy` that categorises variables into three buckets:

- **required** — always forwarded to sandboxed subprocesses (process
  execution, locale, identity, display).
- **optional** — forwarded by default but suppressible via
  ``include_optional=False``; covers API credentials and proxy/TLS vars
  that subprocesses may need to call external services.
- **denied** — *never* forwarded, regardless of other categories; covers
  agent sockets, shell history, and CI-context markers.

This is **process-level isolation** — not container-grade security.  It
reduces ambient environment leakage and bounds the subprocess working
directory, but does not prevent a compromised subprocess from accessing host
resources outside the workspace.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import SandboxBackend


# ---------------------------------------------------------------------------
# Environment variable categories
# ---------------------------------------------------------------------------

#: Variables that are **always** forwarded to sandboxed subprocesses.
#:
#: These are needed for basic process execution, locale/encoding, user
#: identity, and display state.  Absent them, many common tools misbehave.
_REQUIRED_ENV_VARS: frozenset[str] = frozenset({
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

#: Variables forwarded **only when** :attr:`SandboxEnvPolicy.include_optional`
#: is ``True`` (the default).
#:
#: This bucket covers two sub-categories:
#:
#: - *Connectivity* — proxy and TLS settings needed to reach external services.
#: - *Credentials* — API keys for every supported backend.  Subprocesses that
#:   call AI APIs need these; operators running air-gapped workloads may set
#:   ``include_optional=False`` to suppress them entirely.
_OPTIONAL_ENV_VARS: frozenset[str] = frozenset({
    # Network / TLS proxy — needed for backend API calls through subprocesses
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",

    # Anthropic / OpenAI / Google
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_APPLICATION_CREDENTIALS",

    # Azure OpenAI
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",

    # GitHub / Copilot
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "COPILOT_TOKEN",

    # LiteLLM proxy
    "LITELLM_API_KEY",
    "LITELLM_BASE_URL",

    # AWS / Bedrock — credentials and region selection
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
})

#: Variables **never** forwarded to sandboxed subprocesses.
#:
#: These are explicitly denied even if they somehow appear in *required* or
#: *optional* in a custom policy.  Denied always wins.
#:
#: - Agent sockets — prevent sandbox from talking to the host auth agent.
#: - Shell history — no subprocess should be able to read the operator's
#:   command history.
#: - CI markers — leaking CI context into a sandbox can change subprocess
#:   behaviour in unexpected ways (e.g. tools that disable interactivity under
#:   ``CI=true``).
_DENIED_ENV_VARS: frozenset[str] = frozenset({
    # Agent sockets
    "SSH_AUTH_SOCK",
    "GPG_AGENT_INFO",

    # Shell history
    "HISTFILE",
    "HISTSIZE",
    "HISTCONTROL",

    # CI markers
    "CI",
    "GITHUB_ACTIONS",
    "GITHUB_RUN_ID",
    "GITHUB_WORKFLOW",
})


# ---------------------------------------------------------------------------
# Policy dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SandboxEnvPolicy:
    """Structured environment shaping policy for a local-process sandbox.

    Categorises environment variables into three explicit buckets so that
    the intent behind each forwarding decision is always visible and testable.

    Parameters
    ----------
    required_vars:
        Variables always forwarded.  Defaults to :data:`_REQUIRED_ENV_VARS`.
    optional_vars:
        Variables forwarded only when *include_optional* is ``True``.
        Defaults to :data:`_OPTIONAL_ENV_VARS`.
    denied_vars:
        Variables **never** forwarded.  Denied takes precedence over both
        *required_vars* and *optional_vars*.  Defaults to
        :data:`_DENIED_ENV_VARS`.
    include_optional:
        When ``True`` (the default), optional vars are added to the effective
        allowlist.  Set to ``False`` for air-gapped or credential-isolated
        runs.
    """

    required_vars: frozenset[str] = _REQUIRED_ENV_VARS
    optional_vars: frozenset[str] = _OPTIONAL_ENV_VARS
    denied_vars: frozenset[str] = _DENIED_ENV_VARS
    include_optional: bool = True

    def effective_allowlist(self) -> frozenset[str]:
        """Return the effective set of allowed variable names.

        Computation: ``(required | optional_if_active) - denied``.
        Denied always wins — a variable in both *required_vars* and
        *denied_vars* will be excluded from the output.

        Returns
        -------
        frozenset[str]
            Case-sensitive set of env var names that may be forwarded.
        """
        allowed: frozenset[str] = self.required_vars
        if self.include_optional:
            allowed = allowed | self.optional_vars
        return allowed - self.denied_vars

    def strategy_summary(self) -> dict[str, Any]:
        """Return a diagnostic summary of the active env strategy.

        Returns
        -------
        dict[str, Any]
            Keys:

            - ``required`` — number of always-allowed vars.
            - ``optional`` — number of conditionally-allowed vars.
            - ``optional_active`` — whether optional vars are included.
            - ``denied`` — number of explicitly-denied vars.
            - ``effective`` — size of :meth:`effective_allowlist`.
        """
        return {
            "required": len(self.required_vars),
            "optional": len(self.optional_vars),
            "optional_active": self.include_optional,
            "denied": len(self.denied_vars),
            "effective": len(self.effective_allowlist()),
        }


# ---------------------------------------------------------------------------
# Backend implementation
# ---------------------------------------------------------------------------

class LocalProcessBackend(SandboxBackend):
    """Subprocess-based sandbox backend using host filesystem and env policy.

    Parameters
    ----------
    workspace_dir:
        The host filesystem path to use as the execution workspace.
        :meth:`prepare_workspace` creates this directory.
    policy:
        Environment shaping policy.  ``None`` → :class:`SandboxEnvPolicy`
        with default settings (``include_optional=True``).
    """

    def __init__(
        self,
        workspace_dir: Path,
        policy: SandboxEnvPolicy | None = None,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._policy: SandboxEnvPolicy = policy if policy is not None else SandboxEnvPolicy()

    @property
    def policy(self) -> SandboxEnvPolicy:
        """The active environment shaping policy."""
        return self._policy

    def prepare_workspace(self, *, iteration: int | None = None) -> Path:
        """Create the workspace directory and return its path.

        When *iteration* is provided, a per-iteration subdirectory
        ``iter_<NNNN>/`` is created inside the base workspace and returned.
        The base workspace is always created first.

        Idempotent — safe to call multiple times even if the directory
        already exists.

        Parameters
        ----------
        iteration:
            Iteration number.  ``None`` → return the base workspace (existing
            behavior).  Positive int → create and return
            ``<workspace>/iter_<N:04d>/``.

        Returns
        -------
        Path
            The workspace directory path (base or iteration-scoped).
        """
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        if iteration is None:
            return self._workspace_dir
        iter_dir = self._workspace_dir / f"iter_{iteration:04d}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        return iter_dir

    def build_environment(
        self,
        base_env: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Filter *base_env* through the active :class:`SandboxEnvPolicy`.

        Keeps only variables in :meth:`SandboxEnvPolicy.effective_allowlist`.
        Matching is case-insensitive.  The source mapping is never mutated.

        Parameters
        ----------
        base_env:
            Source environment.  ``None`` → :data:`os.environ`.

        Returns
        -------
        dict[str, str]
            A new dict containing only the policy-allowed keys present in
            *base_env*.
        """
        source: Mapping[str, str] = base_env if base_env is not None else os.environ
        allow_upper = {k.upper() for k in self._policy.effective_allowlist()}
        return {k: v for k, v in source.items() if k.upper() in allow_upper}

    def run_subprocess(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Run *argv* as a local subprocess.

        Parameters
        ----------
        argv:
            Command and arguments.  Never passed through a shell.
        cwd:
            Working directory.  ``None`` → inherit from caller.
        env:
            Explicit environment dict.  ``None`` → inherit from caller.
        timeout:
            Seconds before the subprocess is killed.  ``None`` → no timeout.

        Returns
        -------
        tuple[int, str, str]
            ``(returncode, stdout, stderr)``.
        """
        result = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        return (result.returncode, result.stdout, result.stderr)
