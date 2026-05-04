"""MM16 Step 2 — SandboxExecutor.prepare_workspace(iteration=N) and transient sandbox support.

TDD tests written before implementation.

Contract:
  executor.prepare_workspace(iteration=None) → unchanged base workspace behavior
  executor.prepare_workspace(iteration=N)    → delegates to backend; workspace_dir updated to iter path
  write-boundary checks use the current workspace_dir (iter-scoped path accepted)
  _make_transient_sandbox() scope-aware: prepares with right iteration
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from src.policy.sandbox_executor import SandboxExecutor
from src.policy.security_runtime import RuntimeSecurityPolicy
from src.sandbox.backends.local_process import LocalProcessBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(tmp_path: Path, *, sandbox_active: bool = False) -> RuntimeSecurityPolicy:
    output_dir = tmp_path / "output"
    workspace_dir = output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode="sandboxed" if sandbox_active else "direct",
        sandbox_active=sandbox_active,
        _allow_host_bash=False,
        _allow_filesystem_write_outside_output=False,
        _filesystem_access="workspace_only",
        _network_access="none",
        output_dir=output_dir,
        workspace_dir=workspace_dir,
    )


def _make_executor(
    tmp_path: Path, *, sandbox_active: bool = False
) -> SandboxExecutor:
    policy = _make_policy(tmp_path, sandbox_active=sandbox_active)
    return SandboxExecutor(policy, policy.workspace_dir)


# ---------------------------------------------------------------------------
# SandboxExecutor.prepare_workspace(iteration=N) basics
# ---------------------------------------------------------------------------

class TestExecutorPrepareWorkspaceIteration:
    def test_no_arg_unchanged(self, tmp_path):
        """prepare_workspace() (no arg) still returns base workspace."""
        executor = _make_executor(tmp_path)
        path = executor.prepare_workspace()
        assert path == tmp_path / "output" / ".workspace"
        assert path.is_dir()

    def test_iteration_none_unchanged(self, tmp_path):
        """prepare_workspace(iteration=None) returns base workspace."""
        executor = _make_executor(tmp_path)
        path = executor.prepare_workspace(iteration=None)
        assert path == tmp_path / "output" / ".workspace"
        assert path.is_dir()

    def test_iteration_3_returns_iter_path(self, tmp_path):
        """prepare_workspace(iteration=3) returns workspace/iter_0003."""
        executor = _make_executor(tmp_path)
        path = executor.prepare_workspace(iteration=3)
        expected = tmp_path / "output" / ".workspace" / "iter_0003"
        assert path == expected
        assert expected.is_dir()

    def test_iteration_3_updates_workspace_dir(self, tmp_path):
        """After prepare_workspace(iteration=3), workspace_dir reflects iter_0003."""
        executor = _make_executor(tmp_path)
        executor.prepare_workspace(iteration=3)
        assert executor.workspace_dir == tmp_path / "output" / ".workspace" / "iter_0003"

    def test_iteration_99_updates_workspace_dir(self, tmp_path):
        """After prepare_workspace(iteration=99), workspace_dir reflects iter_0099."""
        executor = _make_executor(tmp_path)
        executor.prepare_workspace(iteration=99)
        assert executor.workspace_dir == tmp_path / "output" / ".workspace" / "iter_0099"

    def test_base_workspace_unchanged_before_call(self, tmp_path):
        """workspace_dir is the base path before any prepare_workspace call."""
        executor = _make_executor(tmp_path)
        assert executor.workspace_dir == tmp_path / "output" / ".workspace"

    def test_reset_to_base_with_none(self, tmp_path):
        """Calling prepare_workspace(iteration=None) after iter call resets workspace_dir."""
        executor = _make_executor(tmp_path)
        executor.prepare_workspace(iteration=5)
        assert "iter_0005" in str(executor.workspace_dir)
        executor.prepare_workspace(iteration=None)
        assert executor.workspace_dir == tmp_path / "output" / ".workspace"

    def test_iteration_delegates_to_backend(self, tmp_path):
        """prepare_workspace(iteration=N) forwards iteration=N to the backend."""
        policy = _make_policy(tmp_path)
        mock_backend = MagicMock()
        mock_backend.prepare_workspace.return_value = tmp_path / "output" / ".workspace" / "iter_0003"
        executor = SandboxExecutor(policy, policy.workspace_dir, backend=mock_backend)
        executor.prepare_workspace(iteration=3)
        mock_backend.prepare_workspace.assert_called_once_with(iteration=3)

    def test_no_arg_delegates_none_to_backend(self, tmp_path):
        """prepare_workspace() delegates iteration=None to the backend."""
        policy = _make_policy(tmp_path)
        mock_backend = MagicMock()
        mock_backend.prepare_workspace.return_value = tmp_path / "output" / ".workspace"
        executor = SandboxExecutor(policy, policy.workspace_dir, backend=mock_backend)
        executor.prepare_workspace()
        mock_backend.prepare_workspace.assert_called_once_with(iteration=None)


# ---------------------------------------------------------------------------
# Write-boundary: iter-scoped workspace accepted
# ---------------------------------------------------------------------------

class TestExecutorIterationWriteBoundary:
    def test_write_inside_iter_workspace_accepted(self, tmp_path):
        """After prepare_workspace(iteration=2), writes inside iter_0002 are accepted."""
        executor = _make_executor(tmp_path, sandbox_active=True)
        executor.prepare_workspace(iteration=2)
        # workspace_dir is now iter_0002; writes inside it should be accepted
        write_path = executor.workspace_dir / "output.txt"
        executor.validate_tool_request(action="write", write_path=write_path)

    def test_write_inside_iter_subdir_accepted(self, tmp_path):
        """Writes inside a subdirectory of iter_0002 are also accepted."""
        executor = _make_executor(tmp_path, sandbox_active=True)
        executor.prepare_workspace(iteration=2)
        write_path = executor.workspace_dir / "subdir" / "file.txt"
        executor.validate_tool_request(action="write", write_path=write_path)

    def test_is_within_executor_workspace_iter_path(self, tmp_path):
        """_is_within_executor_workspace returns True for paths inside iter_0003."""
        executor = _make_executor(tmp_path)
        executor.prepare_workspace(iteration=3)
        path = executor.workspace_dir / "some" / "file.txt"
        assert executor._is_within_executor_workspace(path)

    def test_is_within_executor_workspace_different_iter_false(self, tmp_path):
        """A path in iter_0001 is not within iter_0003 workspace."""
        executor = _make_executor(tmp_path)
        executor.prepare_workspace(iteration=3)
        other_iter = tmp_path / "output" / ".workspace" / "iter_0001" / "file.txt"
        assert not executor._is_within_executor_workspace(other_iter)


# ---------------------------------------------------------------------------
# Transient sandbox (via _make_transient_sandbox) iteration support
# ---------------------------------------------------------------------------

class TestTransientSandboxIterationSupport:
    """The transient executor created by _make_transient_sandbox supports iteration workspaces."""

    def _make_transient_executor(self, tmp_path: Path) -> SandboxExecutor:
        """Simulate what _make_transient_sandbox() produces: a fresh executor."""
        policy = _make_policy(tmp_path)
        backend = LocalProcessBackend(policy.workspace_dir)
        return SandboxExecutor(policy, policy.workspace_dir, backend=backend)

    def test_transient_executor_prepare_iteration(self, tmp_path):
        """A transient executor supports prepare_workspace(iteration=N)."""
        executor = self._make_transient_executor(tmp_path)
        path = executor.prepare_workspace(iteration=4)
        assert path == tmp_path / "output" / ".workspace" / "iter_0004"
        assert executor.workspace_dir == path

    def test_transient_executor_accepts_iter_write(self, tmp_path):
        """After prepare_workspace(iteration=1), write inside iter_0001 is accepted."""
        policy = _make_policy(tmp_path, sandbox_active=True)
        backend = LocalProcessBackend(policy.workspace_dir)
        executor = SandboxExecutor(policy, policy.workspace_dir, backend=backend)
        executor.prepare_workspace(iteration=1)
        executor.validate_tool_request(
            action="write",
            write_path=executor.workspace_dir / "artifact.txt",
        )


# ---------------------------------------------------------------------------
# _make_transient_sandbox() is side-effect free
# Iteration-aware prepare_workspace() must be called by _call_with(), not
# inside the factory.
# ---------------------------------------------------------------------------

class TestTransientSandboxSideEffectFree:
    """Verify that _make_transient_sandbox() does NOT call prepare_workspace()."""

    def _make_researcher(self, tmp_path: Path, scope: str = "run"):
        """Build a minimal AutoResearcher with an in-memory FakeBackend."""
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        from src.config import (
            ContainerBackendConfig, ExecutionConfig, ResearchConfig,
            SandboxConfig, ScoringConfig, SecurityConfig,
        )
        sandbox = SandboxConfig(scope=scope)
        config = ResearchConfig(
            topic="T",
            goal="G",
            dimensions=("A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(max_iterations=1, backend="claude-cli", timeout_seconds=5),
            security=SecurityConfig(sandbox=sandbox),
        )
        return AutoResearcher(config=config, backend=FakeBackend(), output_dir=tmp_path / "out")

    def test_transient_sandbox_has_unprepared_workspace(self, tmp_path):
        """_make_transient_sandbox() returns executor; workspace dir NOT yet on disk."""
        researcher = self._make_researcher(tmp_path, scope="run")
        executor = researcher._make_transient_sandbox()
        # The factory must NOT have created the workspace dir as a side effect.
        assert not executor.workspace_dir.exists()

    def test_transient_sandbox_scope_iteration_workspace_not_created(self, tmp_path):
        """With scope=iteration, _make_transient_sandbox() still creates nothing on disk."""
        researcher = self._make_researcher(tmp_path, scope="iteration")
        researcher.iteration = 3  # simulate being mid-run
        executor = researcher._make_transient_sandbox()
        assert not executor.workspace_dir.exists()
        # No iter_0003 dir either
        iter_dir = executor.workspace_dir.parent / "iter_0003"
        assert not iter_dir.exists()


# ---------------------------------------------------------------------------
# _call_with() iteration-aware prepare_workspace invocation
# ---------------------------------------------------------------------------

class TestCallWithIterationScoping:
    """Verify _call_with() passes the right iteration to prepare_workspace."""

    def _make_researcher(self, tmp_path: Path, scope: str = "run"):
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        from src.config import (
            ContainerBackendConfig, ExecutionConfig, ResearchConfig,
            SandboxConfig, ScoringConfig, SecurityConfig,
        )
        sandbox = SandboxConfig(
            scope=scope,
            mode="tool_calls",
        )
        config = ResearchConfig(
            topic="T",
            goal="G",
            dimensions=("A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(max_iterations=1, backend="claude-cli", timeout_seconds=5),
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=sandbox,
            ),
        )
        return AutoResearcher(config=config, backend=FakeBackend(), output_dir=tmp_path / "out")

    def test_scope_run_calls_prepare_with_none(self, tmp_path):
        """scope=run → _call_with passes iteration=None to prepare_workspace."""
        from unittest.mock import patch
        from src.backends import AgentResponse
        researcher = self._make_researcher(tmp_path, scope="run")
        mock_executor = MagicMock()
        mock_executor.policy.sandbox_active = True
        mock_executor.workspace_dir = tmp_path / "ws"
        mock_executor.build_environment.return_value = {}
        researcher._sandbox = mock_executor
        researcher.iteration = 0
        with patch.object(
            researcher.backend, "invoke",
            return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False),
        ):
            researcher._call_with(researcher.backend, "prompt")
        mock_executor.prepare_workspace.assert_called_once_with(iteration=None)

    def test_scope_iteration_with_active_iter_calls_prepare_with_iter(self, tmp_path):
        """scope=iteration + iteration=3 → _call_with passes iteration=3 to prepare_workspace."""
        researcher = self._make_researcher(tmp_path, scope="iteration")
        mock_executor = MagicMock()
        mock_executor.policy.sandbox_active = True
        mock_executor.workspace_dir = tmp_path / "ws"
        mock_executor.build_environment.return_value = {}
        researcher._sandbox = mock_executor
        researcher.iteration = 3
        from unittest.mock import patch
        from src.backends import AgentResponse
        with patch.object(
            researcher.backend, "invoke",
            return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False),
        ):
            researcher._call_with(researcher.backend, "prompt")
        mock_executor.prepare_workspace.assert_called_once_with(iteration=3)

    def test_scope_iteration_with_zero_iter_calls_prepare_with_none(self, tmp_path):
        """scope=iteration but iteration=0 (pre-run) → _call_with passes iteration=None."""
        researcher = self._make_researcher(tmp_path, scope="iteration")
        mock_executor = MagicMock()
        mock_executor.policy.sandbox_active = True
        mock_executor.workspace_dir = tmp_path / "ws"
        mock_executor.build_environment.return_value = {}
        researcher._sandbox = mock_executor
        researcher.iteration = 0
        from unittest.mock import patch
        from src.backends import AgentResponse
        with patch.object(
            researcher.backend, "invoke",
            return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False),
        ):
            researcher._call_with(researcher.backend, "prompt")
        mock_executor.prepare_workspace.assert_called_once_with(iteration=None)
