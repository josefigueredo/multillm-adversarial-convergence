"""Security / sandbox policy types and YAML parsing.

Self-contained module: depends only on stdlib (no other config submodules,
no backends, no top-level src imports). This is intentional — Security
is a leaf concern that other config types compose, not the other way around.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Valid security policy enum values — Milestone 1 contract.
VALID_CONTENT_TRUST = ("strict", "permissive")
VALID_TOOL_EXECUTION_MODES = ("direct", "sandboxed")
VALID_SANDBOX_MODES = ("off", "tool_calls")
VALID_SANDBOX_SCOPES = ("run", "iteration")
VALID_SANDBOX_FILESYSTEM_ACCESS = ("output_only", "workspace_only")
VALID_SANDBOX_NETWORK_ACCESS = ("unrestricted", "web_only", "none")
VALID_SANDBOX_BACKENDS = ("local_process", "container")


@dataclass(frozen=True)
class ContainerBackendConfig:
    """Container-specific configuration for the sandbox backend (MM13).

    Attributes:
        image: OCI image reference to use for the container.
        container_workspace: Absolute path inside the container where the
            host workspace directory will be bind-mounted.  Must start with
            ``/``; relative paths are rejected at construction time.
    """

    image: str = "python:3.11-slim"
    container_workspace: str = "/sandbox/workspace"

    def __post_init__(self) -> None:
        if not self.container_workspace.startswith("/"):
            raise ValueError(
                f"container_workspace must be an absolute path; "
                f"got {self.container_workspace!r}"
            )


@dataclass(frozen=True)
class SandboxConfig:
    """Sandbox isolation settings (policy declaration; enforcement is a later milestone).

    Attributes:
        mode: Sandbox mechanism to use.  ``"off"`` disables isolation;
            ``"process"`` uses process-level isolation; ``"container"`` uses
            container-level isolation.
        scope: Granularity at which isolation is applied.  ``"run"`` wraps
            the whole run; ``"iteration"`` wraps each research iteration;
            ``"call"`` wraps each backend call.
        filesystem_access: Permitted filesystem surface.  ``"output_only"``
            restricts writes to the run output directory; ``"project_only"``
            allows reads/writes within the project root; ``"unrestricted"``
            imposes no restriction.
        network_access: Permitted network surface.  ``"unrestricted"`` allows
            all outbound traffic; ``"restricted"`` blocks non-allow-listed
            destinations; ``"none"`` blocks all outbound traffic.
    """

    mode: str = "off"
    scope: str = "run"
    filesystem_access: str = "output_only"
    network_access: str = "unrestricted"
    backend: str = "local_process"
    container: ContainerBackendConfig = field(default_factory=ContainerBackendConfig)

    def __post_init__(self) -> None:
        if self.scope not in VALID_SANDBOX_SCOPES:
            raise ValueError(
                f"Invalid sandbox.scope {self.scope!r}. "
                f"Must be one of: {', '.join(VALID_SANDBOX_SCOPES)}"
            )


@dataclass(frozen=True)
class SecurityConfig:
    """Security policy model for a research run (policy declaration phase).

    Attributes:
        content_trust: Trust level applied to content returned by backends.
            ``"strict"`` applies conservative sanitization and provenance
            checks; ``"permissive"`` relaxes those checks.
        tool_execution_mode: How tool calls are dispatched.  ``"direct"``
            executes tools without interception; ``"sandboxed"`` routes calls
            through a sandbox; ``"disabled"`` blocks all tool execution.
        allow_host_bash: Whether backend agents are permitted to execute
            host shell commands.  Defaults to ``True`` to match current
            behavior.
        allow_filesystem_write_outside_output: Whether agents may write
            files outside the designated run output directory.  Defaults to
            ``False`` (output-directory-only writes).
        sandbox: Nested sandbox isolation policy.
    """

    content_trust: str = "strict"
    tool_execution_mode: str = "direct"
    allow_host_bash: bool = True
    allow_filesystem_write_outside_output: bool = False
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)


def _parse_security_config(raw: dict[str, Any]) -> "SecurityConfig":
    """Parse and validate a ``security:`` mapping.

    PyYAML (YAML 1.1) silently coerces the bare token ``off`` to the Python
    boolean ``False``.  ``_yaml_str`` recovers the string ``"off"`` for that
    specific case so that ``sandbox.mode: off`` round-trips correctly.
    Any other unexpected boolean is stringified as-is and will fail enum
    validation with a clear error message.
    """

    def _yaml_str(value: Any, default: str) -> str:
        """Coerce a YAML-parsed value to str, recovering ``False -> "off"``."""
        if value is None:
            return default
        if value is False:
            return "off"
        return str(value)

    content_trust = _yaml_str(raw.get("content_trust"), "strict")
    if content_trust not in VALID_CONTENT_TRUST:
        raise ValueError(
            f"Invalid security.content_trust '{content_trust}'. "
            f"Must be one of: {', '.join(VALID_CONTENT_TRUST)}"
        )

    tool_execution_mode = _yaml_str(raw.get("tool_execution_mode"), "direct")
    if tool_execution_mode not in VALID_TOOL_EXECUTION_MODES:
        raise ValueError(
            f"Invalid security.tool_execution_mode '{tool_execution_mode}'. "
            f"Must be one of: {', '.join(VALID_TOOL_EXECUTION_MODES)}"
        )

    sandbox_raw: dict[str, Any] = raw.get("sandbox", {})
    sandbox_mode = _yaml_str(sandbox_raw.get("mode"), "off")
    if sandbox_mode not in VALID_SANDBOX_MODES:
        raise ValueError(
            f"Invalid security.sandbox.mode '{sandbox_mode}'. "
            f"Must be one of: {', '.join(VALID_SANDBOX_MODES)}"
        )
    sandbox_scope = _yaml_str(sandbox_raw.get("scope"), "run")
    if sandbox_scope not in VALID_SANDBOX_SCOPES:
        raise ValueError(
            f"Invalid security.sandbox.scope '{sandbox_scope}'. "
            f"Must be one of: {', '.join(VALID_SANDBOX_SCOPES)}"
        )
    filesystem_access = _yaml_str(sandbox_raw.get("filesystem_access"), "output_only")
    if filesystem_access not in VALID_SANDBOX_FILESYSTEM_ACCESS:
        raise ValueError(
            f"Invalid security.sandbox.filesystem_access '{filesystem_access}'. "
            f"Must be one of: {', '.join(VALID_SANDBOX_FILESYSTEM_ACCESS)}"
        )
    network_access = _yaml_str(sandbox_raw.get("network_access"), "unrestricted")
    if network_access not in VALID_SANDBOX_NETWORK_ACCESS:
        raise ValueError(
            f"Invalid security.sandbox.network_access '{network_access}'. "
            f"Must be one of: {', '.join(VALID_SANDBOX_NETWORK_ACCESS)}"
        )

    sandbox_backend = str(sandbox_raw.get("backend", "local_process"))
    if sandbox_backend not in VALID_SANDBOX_BACKENDS:
        raise ValueError(
            f"Invalid security.sandbox.backend '{sandbox_backend}'. "
            f"Must be one of: {', '.join(VALID_SANDBOX_BACKENDS)}"
        )

    container_raw: dict[str, Any] = sandbox_raw.get("container", {})
    container_cfg = ContainerBackendConfig(
        image=str(container_raw.get("image", "python:3.11-slim")),
        container_workspace=str(
            container_raw.get("container_workspace", "/sandbox/workspace")
        ),
    )

    return SecurityConfig(
        content_trust=content_trust,
        tool_execution_mode=tool_execution_mode,
        allow_host_bash=raw.get("allow_host_bash", True),
        allow_filesystem_write_outside_output=raw.get(
            "allow_filesystem_write_outside_output", False
        ),
        sandbox=SandboxConfig(
            mode=sandbox_mode,
            scope=sandbox_scope,
            filesystem_access=filesystem_access,
            network_access=network_access,
            backend=sandbox_backend,
            container=container_cfg,
        ),
    )
