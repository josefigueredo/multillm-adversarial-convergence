"""Runtime security policy resolution.

Converts a declared ``SecurityConfig`` + ``RunPaths`` into an executable
``RuntimeSecurityPolicy`` — a resolved, immutable object that answers
enforcement questions for a single run.

This module is **pure resolution only**.  No enforcement wiring, no
orchestrator coupling, no I/O side-effects.  Enforcement integration comes
in a subsequent step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import SecurityConfig
    from .run_paths import RunPaths


@dataclass(frozen=True)
class RuntimeSecurityPolicy:
    """Resolved, immutable security policy for one research run.

    Created via :func:`resolve_runtime_security_policy`.  All enforcement
    questions are answered through the methods below — callers never need to
    inspect the raw config fields.

    Attributes:
        tool_execution_mode: Resolved tool execution mode (``"direct"`` or
            ``"sandboxed"``).
        sandbox_active: ``True`` when sandboxing is operationally active.
            Requires both ``tool_execution_mode == "sandboxed"`` **and**
            ``sandbox.mode == "tool_calls"``.  Either flag alone is
            insufficient.
        _allow_host_bash: Whether host-shell execution is permitted.
        _allow_filesystem_write_outside_output: Whether writes outside the
            run output directory are explicitly permitted.
        _filesystem_access: Resolved filesystem access policy token.
        _network_access: Resolved network access policy token.
        output_dir: The run output directory this policy is scoped to.
        workspace_dir: The run-scoped workspace directory (``output_dir /
            ".workspace"``).  Created by the orchestrator for real runs; this
            object only *declares* the path.
    """

    tool_execution_mode: str
    sandbox_active: bool
    _allow_host_bash: bool = field(repr=False)
    _allow_filesystem_write_outside_output: bool = field(repr=False)
    _filesystem_access: str = field(repr=False)
    _network_access: str = field(repr=False)
    output_dir: Path
    workspace_dir: Path

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def is_tool_execution_allowed(self) -> bool:
        """Return ``True`` when tool execution is permitted under this policy.

        In Milestone 2, both ``"direct"`` and ``"sandboxed"`` permit
        execution; ``"sandboxed"`` additionally sets :attr:`sandbox_active`
        when ``sandbox.mode == "tool_calls"``.
        Hard-blocking is deferred until a real sandbox backend is available.
        """
        return self.tool_execution_mode in ("direct", "sandboxed")

    # ------------------------------------------------------------------
    # Host bash
    # ------------------------------------------------------------------

    def is_host_bash_allowed(self) -> bool:
        """Return ``True`` when host shell execution is permitted."""
        return self._allow_host_bash

    # ------------------------------------------------------------------
    # Filesystem writes
    # ------------------------------------------------------------------

    def writes_outside_output_allowed(self) -> bool:
        """Return ``True`` when writes outside the run output directory are
        explicitly permitted by ``allow_filesystem_write_outside_output``."""
        return self._allow_filesystem_write_outside_output

    def allowed_write_roots(self) -> list[Path]:
        """Return the list of directory roots that tool writes are permitted within.

        - ``"output_only"`` → ``[output_dir]``
        - ``"workspace_only"`` → ``[workspace_dir]``

        Note: when :meth:`writes_outside_output_allowed` returns ``True``,
        the declared ``filesystem_access`` scope still applies for the
        *default* roots, but :meth:`is_write_allowed` will permit any path.
        """
        if self._filesystem_access == "workspace_only":
            return [self.workspace_dir]
        # "output_only" (the default)
        return [self.output_dir]

    def is_write_allowed(self, path: Path) -> bool:
        """Return ``True`` when *path* is a permitted write destination.

        If ``allow_filesystem_write_outside_output`` is ``True``, all paths
        are permitted (the operator explicitly declared broad write access).
        Otherwise the path must fall within :meth:`allowed_write_roots`.
        """
        if self._allow_filesystem_write_outside_output:
            return True
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path.absolute()
        for root in self.allowed_write_roots():
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def network_mode(self) -> str:
        """Return the resolved network access token."""
        return self._network_access

    @property
    def filesystem_access(self) -> str:
        """Return the resolved filesystem access policy token."""
        return self._filesystem_access

    def is_network_allowed(self, *, destination_type: str) -> bool:
        """Return ``True`` when outbound traffic to *destination_type* is permitted.

        Args:
            destination_type: ``"web"`` for HTTP/HTTPS destinations, ``"other"``
                for anything else (internal services, arbitrary TCP, etc.).
        """
        mode = self._network_access
        if mode == "unrestricted":
            return True
        if mode == "none":
            return False
        if mode == "web_only":
            return destination_type == "web"
        return False


def resolve_runtime_security_policy(
    security: "SecurityConfig",
    paths: "RunPaths",
) -> RuntimeSecurityPolicy:
    """Resolve a :class:`~src.config.SecurityConfig` into a
    :class:`RuntimeSecurityPolicy` scoped to *paths*.

    ``sandbox_active`` requires *both* conditions to be true:

    - ``tool_execution_mode == "sandboxed"``
    - ``sandbox.mode == "tool_calls"``

    Either condition alone is insufficient.

    This is a pure function — it performs no I/O and has no side-effects.
    """
    sandbox_active = (
        security.tool_execution_mode == "sandboxed"
        and security.sandbox.mode == "tool_calls"
    )
    workspace_dir = paths.output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode=security.tool_execution_mode,
        sandbox_active=sandbox_active,
        _allow_host_bash=security.allow_host_bash,
        _allow_filesystem_write_outside_output=security.allow_filesystem_write_outside_output,
        _filesystem_access=security.sandbox.filesystem_access,
        _network_access=security.sandbox.network_access,
        output_dir=paths.output_dir,
        workspace_dir=workspace_dir,
    )
