"""ContainerBackend.run_subprocess() via docker run.

TDD tests written before implementation.

All tests mock subprocess.run — no live Docker required.

Contract:
- Builds docker argv: docker run --rm --mount ... [--env K=V ...] image *argv
- No shell, no string interpolation
- timeout forwarded to subprocess.run
- Returns (returncode, stdout, stderr) normalized tuple
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.sandbox.backends.container import ContainerBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(tmp_path: Path, image: str = "python:3.11-slim") -> ContainerBackend:
    return ContainerBackend(
        image=image,
        host_workspace=tmp_path / "host_ws",
        container_workspace="/sandbox/workspace",
    )


def _mock_run(returncode: int = 0, stdout: str = "out", stderr: str = "") -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Docker argv structure
# ---------------------------------------------------------------------------

class TestContainerBackendRunSubprocessArgv:
    def test_rm_flag_present(self, tmp_path):
        """--rm is always included so containers are cleaned up."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["echo", "hi"])
            argv = mock_run.call_args[0][0]
            assert "--rm" in argv

    def test_docker_run_command(self, tmp_path):
        """Argv begins with ['docker', 'run']."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["echo", "hi"])
            argv = mock_run.call_args[0][0]
            assert argv[0] == "docker"
            assert argv[1] == "run"

    def test_mount_flag_present(self, tmp_path):
        """--mount is included in docker argv."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["echo", "hi"])
            argv = mock_run.call_args[0][0]
            assert "--mount" in argv

    def test_mount_contains_host_workspace(self, tmp_path):
        """--mount value references the host workspace path."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            argv = mock_run.call_args[0][0]
            mount_idx = argv.index("--mount")
            mount_val = argv[mount_idx + 1]
            assert f"source={backend.host_workspace}" in mount_val

    def test_mount_contains_container_workspace(self, tmp_path):
        """--mount value references the container workspace path."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            argv = mock_run.call_args[0][0]
            mount_idx = argv.index("--mount")
            mount_val = argv[mount_idx + 1]
            assert f"target={backend.container_workspace}" in mount_val

    def test_mount_type_bind(self, tmp_path):
        """--mount uses type=bind."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            argv = mock_run.call_args[0][0]
            mount_idx = argv.index("--mount")
            mount_val = argv[mount_idx + 1]
            assert "type=bind" in mount_val

    def test_image_immediately_before_user_argv(self, tmp_path):
        """Image name comes right before the user argv."""
        image = "myrepo/myimage:latest"
        backend = ContainerBackend(
            image=image,
            host_workspace=tmp_path / "ws",
            container_workspace="/sandbox/workspace",
        )
        user_argv = ["python3", "-c", "print(1)"]
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(user_argv)
            argv = mock_run.call_args[0][0]
            img_idx = argv.index(image)
            assert argv[img_idx + 1 :] == user_argv

    def test_user_argv_appended_after_image(self, tmp_path):
        """All user argv elements are present after the image."""
        backend = _make_backend(tmp_path)
        user_argv = ["echo", "hello", "world"]
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(user_argv)
            argv = mock_run.call_args[0][0]
            img_idx = argv.index(backend.image)
            assert argv[img_idx + 1 :] == user_argv


# ---------------------------------------------------------------------------
# Env forwarding
# ---------------------------------------------------------------------------

class TestContainerBackendRunSubprocessEnv:
    def test_no_env_args_when_env_is_none(self, tmp_path):
        """When env=None, no --env flags are added."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], env=None)
            argv = mock_run.call_args[0][0]
            assert "--env" not in argv

    def test_env_key_value_pairs_added(self, tmp_path):
        """Each env key produces a ['--env', 'KEY=VALUE'] pair."""
        backend = _make_backend(tmp_path)
        env = {"FOO": "bar", "BAZ": "qux"}
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], env=env)
            argv = mock_run.call_args[0][0]
            env_pairs = {}
            i = 0
            while i < len(argv):
                if argv[i] == "--env" and i + 1 < len(argv):
                    k, _, v = argv[i + 1].partition("=")
                    env_pairs[k] = v
                    i += 2
                else:
                    i += 1
            for key, val in env.items():
                assert key in env_pairs, f"Missing env key {key}"
                assert env_pairs[key] == val

    def test_env_before_image(self, tmp_path):
        """All --env flags appear before the image name in docker argv."""
        backend = _make_backend(tmp_path)
        env = {"MY_VAR": "42"}
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], env=env)
            argv = mock_run.call_args[0][0]
            env_indices = [i for i, a in enumerate(argv) if a == "--env"]
            img_idx = argv.index(backend.image)
            assert all(idx < img_idx for idx in env_indices)


# ---------------------------------------------------------------------------
# subprocess.run call kwargs
# ---------------------------------------------------------------------------

class TestContainerBackendRunSubprocessKwargs:
    def test_no_shell_flag(self, tmp_path):
        """Subprocess.run must NOT use shell=True."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            _, kwargs = mock_run.call_args
            assert not kwargs.get("shell", False)

    def test_capture_output_and_text(self, tmp_path):
        """Capture_output=True and text=True so we get str stdout/stderr."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            _, kwargs = mock_run.call_args
            assert kwargs.get("capture_output") is True
            assert kwargs.get("text") is True

    def test_timeout_forwarded(self, tmp_path):
        """Timeout is forwarded to subprocess.run."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], timeout=15.0)
            _, kwargs = mock_run.call_args
            assert kwargs.get("timeout") == 15.0

    def test_timeout_none_when_not_provided(self, tmp_path):
        """When timeout is not given, it is None (no timeout)."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"])
            _, kwargs = mock_run.call_args
            assert kwargs.get("timeout") is None


# ---------------------------------------------------------------------------
# Working directory (--workdir) semantics
# ---------------------------------------------------------------------------

class TestContainerBackendRunSubprocessWorkdir:
    def test_explicit_cwd_becomes_workdir(self, tmp_path):
        """When cwd is given, docker argv includes --workdir <cwd>."""
        backend = _make_backend(tmp_path)
        custom_cwd = Path("/sandbox/workspace/subdir")
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], cwd=custom_cwd)
            argv = mock_run.call_args[0][0]
            assert "--workdir" in argv
            wdir_idx = argv.index("--workdir")
            assert argv[wdir_idx + 1] == str(custom_cwd)

    def test_none_cwd_defaults_to_container_workspace(self, tmp_path):
        """When cwd=None, --workdir defaults to the container workspace path."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], cwd=None)
            argv = mock_run.call_args[0][0]
            assert "--workdir" in argv
            wdir_idx = argv.index("--workdir")
            assert argv[wdir_idx + 1] == backend.container_workspace

    def test_workdir_before_image(self, tmp_path):
        """--workdir flag appears before the image name in docker argv."""
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run()) as mock_run:
            backend.run_subprocess(["ls"], cwd=Path("/sandbox/workspace"))
            argv = mock_run.call_args[0][0]
            wdir_idx = argv.index("--workdir")
            img_idx = argv.index(backend.image)
            assert wdir_idx < img_idx


# ---------------------------------------------------------------------------
# Return value passthrough
# ---------------------------------------------------------------------------

class TestContainerBackendRunSubprocessReturn:
    def test_returncode_passed_through(self, tmp_path):
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run(returncode=42)):
            rc, _, _ = backend.run_subprocess(["false"])
            assert rc == 42

    def test_stdout_passed_through(self, tmp_path):
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run(stdout="container output\n")):
            _, out, _ = backend.run_subprocess(["echo", "hi"])
            assert out == "container output\n"

    def test_stderr_passed_through(self, tmp_path):
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run(stderr="error text")):
            _, _, err = backend.run_subprocess(["cmd"])
            assert err == "error text"

    def test_zero_returncode_success(self, tmp_path):
        backend = _make_backend(tmp_path)
        with patch("subprocess.run", return_value=_mock_run(returncode=0, stdout="ok")):
            rc, out, err = backend.run_subprocess(["ls"])
            assert rc == 0
            assert out == "ok"
            assert err == ""
