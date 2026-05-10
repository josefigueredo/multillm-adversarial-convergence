"""Tests for src.backends.base — Backend ABC, check_available, _run_process."""

import os
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from src.backends.base import Backend
from src.backends.claude import ClaudeBackend
from src.backends.codex import CodexBackend
from src.backends.gemini import GeminiBackend


class TestCheckAvailable:
    @patch("src.backends.base.subprocess.run")
    def test_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert ClaudeBackend().check_available() is True

    @patch("src.backends.base.subprocess.run")
    def test_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert CodexBackend().check_available() is False

    @patch("src.backends.base.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gemini-cli", timeout=10)
        assert GeminiBackend().check_available() is False


class TestRunProcessTimeoutDoesNotKillParent:
    """Regression guard for the 'killed mid-compress' bug.

    Pre-fix: ``_run_process`` did not pass ``start_new_session=True`` on POSIX,
    so when the timeout fired the call to ``os.killpg(getpgid(child), SIGKILL)``
    sent SIGKILL to the *parent's* process group too — the python interpreter
    died alongside the child. This was originally diagnosed as OOM but was
    really the timeout signal taking out the test runner.

    These tests fork a real shell ``sleep 30`` with a 1s timeout and assert:
      1. ``TimeoutExpired`` is raised (the timeout path actually triggered)
      2. The parent process (this pytest worker) is still alive afterwards —
         trivially proven by the assertion line being reached
      3. On POSIX the child was launched in its own session/PG, which is
         what makes ``killpg`` safe.

    Skipped on Windows because the Windows path uses ``taskkill`` and a
    ``CREATE_NEW_PROCESS_GROUP`` flag — covered by separate Windows tests.
    """

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific session/PG behaviour")
    def test_timeout_raises_without_killing_parent(self):
        parent_pgid_before = os.getpgid(0)

        with pytest.raises(subprocess.TimeoutExpired):
            Backend._run_process(
                ["sleep", "30"],
                input=None,
                timeout=1,
            )

        # Reaching this line proves the parent survived the killpg call.
        # Belt-and-suspenders: confirm our own process group is unchanged.
        assert os.getpgid(0) == parent_pgid_before

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific session/PG behaviour")
    def test_child_runs_in_own_session(self):
        """Probe that the spawned child is in a different session from us.

        The child runs Python and prints its own session id to stdout. The
        parent reads stdout and asserts the SID differs from the parent's.
        Using python (not ``ps``) keeps this portable across BSD/Linux ps
        flag differences.
        """
        cmd = [sys.executable, "-c", "import os; print(os.getsid(os.getpid()))"]

        result = Backend._run_process(cmd, input=None, timeout=10)
        assert result.returncode == 0, f"unexpected stderr: {result.stderr!r}"

        child_sid = int(result.stdout.strip())
        parent_sid = os.getsid(0)
        assert child_sid != parent_sid, (
            "child must run in its own session so killpg(child) doesn't hit parent"
        )

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific session/PG behaviour")
    def test_timeout_actually_terminates_child(self):
        """Timeout must kill the child; otherwise leaked processes pile up across iterations."""
        # Spawn a long-lived child, hit timeout fast, then verify it's gone.
        # Use a sentinel approach: write PID to disk, then sleep; after the
        # timeout, sending signal 0 to that PID should fail.
        import tempfile
        with tempfile.NamedTemporaryFile(mode="r+", delete=False) as f:
            pid_file = f.name
        try:
            cmd = ["sh", "-c", f"echo $$ > {pid_file}; sleep 30"]
            with pytest.raises(subprocess.TimeoutExpired):
                Backend._run_process(cmd, input=None, timeout=1)

            # Give the SIGKILL a moment to propagate
            time.sleep(0.1)
            with open(pid_file) as f:
                child_pid = int(f.read().strip())
            # signal 0 is the existence probe; raises if pid is gone
            with pytest.raises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            try:
                os.unlink(pid_file)
            except OSError:
                pass
