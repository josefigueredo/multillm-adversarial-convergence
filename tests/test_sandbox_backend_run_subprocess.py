"""Run_subprocess on SandboxBackend ABC and LocalProcessBackend.

TDD tests written before implementation.

Contract:
- SandboxBackend.run_subprocess(argv: list[str], *, cwd, env, timeout)
  -> tuple[int, str, str]  (returncode, stdout, stderr)
- LocalProcessBackend delegates to subprocess.run; no shell; argv-based.
- A concrete subclass that omits run_subprocess raises TypeError on instantiation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sandbox.backends.base import SandboxBackend
from src.sandbox.backends.local_process import LocalProcessBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MinimalConcreteBackend(SandboxBackend):
    """Implements prepare_workspace and build_environment but NOT run_subprocess."""

    def prepare_workspace(self) -> Path:
        return Path("/tmp/test")

    def build_environment(self, base_env=None) -> dict:
        return {}

    # run_subprocess intentionally omitted → should raise TypeError


class _FullConcreteBackend(SandboxBackend):
    """Implements all three abstract methods — used to verify contract shape."""

    def prepare_workspace(self) -> Path:
        return Path("/tmp/test")

    def build_environment(self, base_env=None) -> dict:
        return {}

    def run_subprocess(self, argv, *, cwd=None, env=None, timeout=None):
        return (0, "ok", "")


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------

class TestSandboxBackendABCRunSubprocess:
    def test_missing_run_subprocess_raises_type_error(self):
        """Concrete subclass omitting run_subprocess cannot be instantiated."""
        with pytest.raises(TypeError):
            _MinimalConcreteBackend()  # type: ignore[abstract]

    def test_full_concrete_backend_instantiates(self):
        """A subclass implementing all three methods instantiates cleanly."""
        backend = _FullConcreteBackend()
        assert backend is not None

    def test_return_shape(self):
        """Run_subprocess returns a 3-tuple (returncode, stdout, stderr)."""
        backend = _FullConcreteBackend()
        result = backend.run_subprocess(["echo", "hi"])
        assert isinstance(result, tuple)
        assert len(result) == 3
        returncode, stdout, stderr = result
        assert isinstance(returncode, int)
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)


# ---------------------------------------------------------------------------
# LocalProcessBackend.run_subprocess
# ---------------------------------------------------------------------------

class TestLocalProcessBackendRunSubprocess:
    def test_echo_hello_returns_zero_and_stdout(self, tmp_path):
        backend = LocalProcessBackend(tmp_path)
        rc, out, err = backend.run_subprocess(["echo", "hello"])
        assert rc == 0
        assert "hello" in out
        assert err == ""

    def test_false_returns_nonzero(self, tmp_path):
        backend = LocalProcessBackend(tmp_path)
        rc, out, err = backend.run_subprocess(["false"])
        assert rc != 0

    def test_cwd_forwarded(self, tmp_path):
        """Cwd parameter is forwarded to subprocess.run."""
        backend = LocalProcessBackend(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="out", stderr=""
            )
            backend.run_subprocess(["ls"], cwd=tmp_path)
            _, kwargs = mock_run.call_args
            assert kwargs["cwd"] == tmp_path

    def test_env_forwarded(self, tmp_path):
        """Env parameter is forwarded to subprocess.run."""
        backend = LocalProcessBackend(tmp_path)
        custom_env = {"PATH": "/usr/bin", "MY_VAR": "42"}
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            backend.run_subprocess(["env"], env=custom_env)
            _, kwargs = mock_run.call_args
            assert kwargs["env"] == custom_env

    def test_timeout_forwarded(self, tmp_path):
        """Timeout parameter is forwarded to subprocess.run."""
        backend = LocalProcessBackend(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            backend.run_subprocess(["sleep", "0"], timeout=5.0)
            _, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 5.0

    def test_no_shell_flag(self, tmp_path):
        """Subprocess.run is called WITHOUT shell=True (no shell injection surface)."""
        backend = LocalProcessBackend(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            backend.run_subprocess(["echo", "test"])
            _, kwargs = mock_run.call_args
            assert not kwargs.get("shell", False)

    def test_capture_output_enabled(self, tmp_path):
        """Capture_output=True and text=True so we get str stdout/stderr."""
        backend = LocalProcessBackend(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            backend.run_subprocess(["echo", "test"])
            _, kwargs = mock_run.call_args
            assert kwargs.get("capture_output") is True
            assert kwargs.get("text") is True

    def test_stderr_captured(self, tmp_path):
        """Stderr from the subprocess is captured in the third tuple element."""
        backend = LocalProcessBackend(tmp_path)
        # Use a command that writes to stderr
        rc, out, err = backend.run_subprocess(
            ["python3", "-c", "import sys; sys.stderr.write('err_msg')"]
        )
        assert "err_msg" in err
