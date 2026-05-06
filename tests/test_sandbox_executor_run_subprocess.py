"""SandboxExecutor.run_subprocess() delegation.

TDD tests written before implementation.

Contract:
- SandboxExecutor.run_subprocess(argv, *, timeout) -> tuple[int, str, str]
- Calls self._backend.build_environment() FIRST, then passes result as env=
- Passes cwd=self._workspace_dir (the executor's authoritative workspace)
- Returns the normalized tuple from the backend unchanged
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sandbox.backends.container import ContainerBackend
from src.sandbox.backends.local_process import LocalProcessBackend
from src.policy.sandbox_executor import SandboxExecutor
from src.policy.security_runtime import RuntimeSecurityPolicy


def _make_policy(tmp_path: Path) -> RuntimeSecurityPolicy:
    output_dir = tmp_path / "output"
    workspace_dir = output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode="sandboxed",
        sandbox_active=True,
        _allow_host_bash=False,
        _allow_filesystem_write_outside_output=False,
        _filesystem_access="output_only",
        _network_access="unrestricted",
        output_dir=output_dir,
        workspace_dir=workspace_dir,
    )


def _make_executor(tmp_path: Path, backend=None) -> SandboxExecutor:
    policy = _make_policy(tmp_path)
    workspace_dir = tmp_path / "output" / ".workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return SandboxExecutor(policy, workspace_dir, backend=backend)


class TestSandboxExecutorRunSubprocessDelegation:
    def test_delegates_to_backend(self, tmp_path):
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = {"PATH": "/usr/bin"}
        mock_backend.run_subprocess.return_value = (0, "delegated", "")
        executor = _make_executor(tmp_path, backend=mock_backend)
        rc, out, err = executor.run_subprocess(["echo", "hi"])
        mock_backend.run_subprocess.assert_called_once()
        assert (rc, out, err) == (0, "delegated", "")

    def test_cwd_is_executor_workspace_dir(self, tmp_path):
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = {}
        mock_backend.run_subprocess.return_value = (0, "", "")
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.run_subprocess(["ls"])
        _, kwargs = mock_backend.run_subprocess.call_args
        assert kwargs["cwd"] == executor.workspace_dir

    def test_env_comes_from_build_environment(self, tmp_path):
        filtered_env = {"PATH": "/usr/bin", "HOME": "/home/user"}
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = filtered_env
        mock_backend.run_subprocess.return_value = (0, "", "")
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.run_subprocess(["env"])
        _, kwargs = mock_backend.run_subprocess.call_args
        assert kwargs["env"] == filtered_env

    def test_build_environment_called_before_run_subprocess(self, tmp_path):
        call_order: list[str] = []
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.side_effect = lambda *a, **kw: (
            call_order.append("build_environment") or {}
        )
        mock_backend.run_subprocess.side_effect = lambda *a, **kw: (
            call_order.append("run_subprocess") or (0, "", "")
        )
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.run_subprocess(["ls"])
        assert call_order == ["build_environment", "run_subprocess"]

    def test_timeout_forwarded(self, tmp_path):
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = {}
        mock_backend.run_subprocess.return_value = (0, "", "")
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.run_subprocess(["sleep", "1"], timeout=10.0)
        _, kwargs = mock_backend.run_subprocess.call_args
        assert kwargs["timeout"] == 10.0

    def test_timeout_defaults_to_none(self, tmp_path):
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = {}
        mock_backend.run_subprocess.return_value = (0, "", "")
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.run_subprocess(["ls"])
        _, kwargs = mock_backend.run_subprocess.call_args
        assert kwargs["timeout"] is None

    def test_return_value_passed_through(self, tmp_path):
        mock_backend = MagicMock(spec=LocalProcessBackend)
        mock_backend.build_environment.return_value = {}
        mock_backend.run_subprocess.return_value = (42, "out", "err")
        executor = _make_executor(tmp_path, backend=mock_backend)
        assert executor.run_subprocess(["cmd"]) == (42, "out", "err")


class TestSandboxExecutorRunSubprocessLocalIntegration:
    def test_local_echo_integration(self, tmp_path):
        backend = LocalProcessBackend(tmp_path / "ws")
        (tmp_path / "ws").mkdir(parents=True, exist_ok=True)
        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(policy, tmp_path / "ws", backend=backend)
        rc, out, err = executor.run_subprocess(["echo", "hi"])
        assert rc == 0
        assert "hi" in out
        assert err == ""


class TestSandboxExecutorRunSubprocessContainerIntegration:
    def test_container_docker_argv_uses_executor_workspace(self, tmp_path):
        host_ws = tmp_path / "host_ws"
        host_ws.mkdir(parents=True, exist_ok=True)
        container_ws = "/sandbox/workspace"
        backend = ContainerBackend(
            image="python:3.11-slim",
            host_workspace=host_ws,
            container_workspace=container_ws,
        )
        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(policy, Path(container_ws), backend=backend)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            executor.run_subprocess(["ls"])
            docker_argv = mock_run.call_args[0][0]
            assert "--workdir" in docker_argv
            wdir_idx = docker_argv.index("--workdir")
            assert docker_argv[wdir_idx + 1] == str(executor.workspace_dir)

    def test_container_env_from_build_environment(self, tmp_path):
        host_ws = tmp_path / "host_ws"
        host_ws.mkdir(parents=True, exist_ok=True)
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=host_ws)
        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(
            policy, Path(backend.container_workspace), backend=backend
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            executor.run_subprocess(["env"])
            docker_argv = mock_run.call_args[0][0]
            env_from_backend = backend.build_environment()
            for key, val in env_from_backend.items():
                assert f"{key}={val}" in docker_argv
