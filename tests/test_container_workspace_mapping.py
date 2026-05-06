"""Workspace/env/write semantics mapped onto container execution.

TDD tests that verify:
- workspace_dir updates to the container-side path after prepare_workspace()
- write-boundary validation accepts container-workspace paths
- write-boundary validation still denies paths outside the workspace
- build_environment() with container backend applies the stricter allowlist
- SandboxExecutor + ContainerBackend integrates with select_sandbox_backend
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.policy.policy_denial import PolicyDeniedError
from src.policy.sandbox_executor import SandboxExecutor
from src.policy.security_runtime import RuntimeSecurityPolicy


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_policy(
    tmp_path: Path,
    *,
    filesystem_access: str = "workspace_only",
    network_access: str = "unrestricted",
    sandbox_active: bool = True,
) -> RuntimeSecurityPolicy:
    output_dir = tmp_path / "output"
    workspace_dir = output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode="sandboxed",
        sandbox_active=sandbox_active,
        _allow_host_bash=False,
        _allow_filesystem_write_outside_output=False,
        _filesystem_access=filesystem_access,
        _network_access=network_access,
        output_dir=output_dir,
        workspace_dir=workspace_dir,
    )


def _make_container_executor(
    tmp_path: Path,
    *,
    image: str = "python:3.11-slim",
    container_workspace: str = "/sandbox/workspace",
    filesystem_access: str = "workspace_only",
) -> SandboxExecutor:
    from src.sandbox.backends.container import ContainerBackend
    policy = _make_policy(tmp_path, filesystem_access=filesystem_access)
    host_ws = tmp_path / "output" / ".workspace"
    backend = ContainerBackend(
        image=image,
        host_workspace=host_ws,
        container_workspace=container_workspace,
    )
    return SandboxExecutor(policy, host_ws, backend=backend)


# ══════════════════════════════════════════════════════════════════════════════
# Workspace path mapping
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkspacePathMapping:
    def test_workspace_dir_is_host_path_before_prepare(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        # Before prepare, workspace_dir is the host workspace passed at construction
        assert executor.workspace_dir == tmp_path / "output" / ".workspace"

    def test_workspace_dir_becomes_container_path_after_prepare(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        executor.prepare_workspace()
        assert executor.workspace_dir == Path("/sandbox/workspace")

    def test_prepare_workspace_returns_container_path(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        result = executor.prepare_workspace()
        assert result == Path("/sandbox/workspace")

    def test_prepare_workspace_creates_host_directory(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        host_ws = tmp_path / "output" / ".workspace"
        assert not host_ws.exists()
        executor.prepare_workspace()
        assert host_ws.exists()

    def test_custom_container_workspace_respected(self, tmp_path: Path):
        executor = _make_container_executor(
            tmp_path, container_workspace="/custom/exec"
        )
        result = executor.prepare_workspace()
        assert result == Path("/custom/exec")


# ══════════════════════════════════════════════════════════════════════════════
# Write-boundary semantics mapped onto container execution
# ══════════════════════════════════════════════════════════════════════════════

class TestContainerWriteBoundary:
    def test_write_within_container_workspace_allowed_after_prepare(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        executor.prepare_workspace()
        # Write to a path inside the container workspace — should be allowed
        executor.validate_tool_request(
            "write_file",
            write_path=Path("/sandbox/workspace/output.txt"),
        )

    def test_write_to_container_workspace_root_allowed(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        executor.prepare_workspace()
        executor.validate_tool_request(
            "write_file",
            write_path=Path("/sandbox/workspace"),
        )

    def test_write_outside_container_workspace_denied(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        executor.prepare_workspace()
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(
                "write_secret",
                write_path=Path("/tmp/secret.txt"),
            )
        assert exc_info.value.reason_code == "write_outside_allowed_roots"

    def test_write_to_container_root_denied(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        executor.prepare_workspace()
        with pytest.raises(PolicyDeniedError):
            executor.validate_tool_request(
                "write_root",
                write_path=Path("/etc/passwd"),
            )

    def test_write_boundary_without_prepare_uses_host_path(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        # Before prepare_workspace(), workspace_dir is still the host path.
        # Write to that host workspace should be allowed.
        executor.validate_tool_request(
            "write_file",
            write_path=tmp_path / "output" / ".workspace" / "result.txt",
        )


# ══════════════════════════════════════════════════════════════════════════════
# Environment shaping mapped onto container execution
# ══════════════════════════════════════════════════════════════════════════════

class TestContainerEnvironmentMapping:
    def test_build_environment_returns_dict(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        env = executor.build_environment()
        assert isinstance(env, dict)

    def test_build_environment_strips_api_keys(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        base = {
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-secret",
            "AWS_SECRET_ACCESS_KEY": "aws-secret",
        }
        env = executor.build_environment(base_env=base)
        assert "ANTHROPIC_API_KEY" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env

    def test_build_environment_passes_safe_vars(self, tmp_path: Path):
        executor = _make_container_executor(tmp_path)
        base = {"PATH": "/usr/bin", "HOME": "/root"}
        env = executor.build_environment(base_env=base)
        # PATH and HOME are in the container allowlist
        assert "PATH" in env or "HOME" in env  # at least one safe var passes


# ══════════════════════════════════════════════════════════════════════════════
# Integration: SandboxExecutor + select_sandbox_backend
# ══════════════════════════════════════════════════════════════════════════════

class TestSelectSandboxBackendIntegration:
    def test_executor_with_selected_container_backend(self, tmp_path: Path):
        from src.config import ContainerBackendConfig, SandboxConfig
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.container import ContainerBackend

        cfg = SandboxConfig(
            backend="container",
            container=ContainerBackendConfig(
                image="python:3.11-slim",
                container_workspace="/sandbox/workspace",
            ),
        )
        backend = select_sandbox_backend(cfg, tmp_path)
        assert isinstance(backend, ContainerBackend)

        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(policy, tmp_path / ".workspace", backend=backend)
        result = executor.prepare_workspace()
        assert result == Path("/sandbox/workspace")

    def test_executor_with_selected_local_process_backend(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.local_process import LocalProcessBackend

        cfg = SandboxConfig(backend="local_process")
        backend = select_sandbox_backend(cfg, tmp_path)
        assert isinstance(backend, LocalProcessBackend)

        policy = _make_policy(tmp_path)
        host_ws = tmp_path / ".workspace"
        executor = SandboxExecutor(policy, host_ws, backend=backend)
        result = executor.prepare_workspace()
        assert result == host_ws
