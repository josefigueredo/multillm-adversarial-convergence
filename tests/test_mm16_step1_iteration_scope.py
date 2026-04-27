"""MM16 Step 1 — iteration scope: config + backend prepare_workspace path contract.

TDD tests written before implementation.

Pinned path contract:
  iteration=None → existing behavior (run-scoped workspace)
  iteration=1    → workspace/iter_0001/  (created + returned)
  iteration=99   → workspace/iter_0099/
  container:
  iteration=2    → /sandbox/workspace/iter_0002  (host subdir created)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config import SandboxConfig, VALID_SANDBOX_SCOPES
from src.sandbox.backends.container import ContainerBackend
from src.sandbox.backends.local_process import LocalProcessBackend


# ---------------------------------------------------------------------------
# Config: scope="iteration" is now valid
# ---------------------------------------------------------------------------

class TestSandboxConfigIterationScope:
    def test_iteration_in_valid_scopes(self):
        """VALID_SANDBOX_SCOPES includes 'iteration'."""
        assert "iteration" in VALID_SANDBOX_SCOPES

    def test_run_still_valid(self):
        """scope='run' is still valid."""
        assert "run" in VALID_SANDBOX_SCOPES

    def test_scope_call_still_invalid(self):
        """scope='call' is still rejected — only run and iteration are valid."""
        with pytest.raises(ValueError, match="scope"):
            SandboxConfig(scope="call")

    def test_sandbox_config_scope_iteration_accepted(self):
        """SandboxConfig(scope='iteration') constructs without error."""
        cfg = SandboxConfig(scope="iteration")
        assert cfg.scope == "iteration"


# ---------------------------------------------------------------------------
# LocalProcessBackend: prepare_workspace with iteration
# ---------------------------------------------------------------------------

class TestLocalProcessBackendIterationWorkspace:
    def test_none_iteration_unchanged(self, tmp_path):
        """iteration=None returns the top-level workspace (existing behavior)."""
        backend = LocalProcessBackend(tmp_path / "ws")
        path = backend.prepare_workspace(iteration=None)
        assert path == tmp_path / "ws"
        assert path.exists()

    def test_no_arg_unchanged(self, tmp_path):
        """prepare_workspace() (no arg) behaves identically to iteration=None."""
        backend = LocalProcessBackend(tmp_path / "ws")
        path = backend.prepare_workspace()
        assert path == tmp_path / "ws"
        assert path.exists()

    def test_iteration_1_creates_iter_0001(self, tmp_path):
        """iteration=1 creates and returns workspace/iter_0001/."""
        backend = LocalProcessBackend(tmp_path / "ws")
        path = backend.prepare_workspace(iteration=1)
        expected = tmp_path / "ws" / "iter_0001"
        assert path == expected
        assert expected.is_dir()

    def test_iteration_99_creates_iter_0099(self, tmp_path):
        """iteration=99 creates and returns workspace/iter_0099/."""
        backend = LocalProcessBackend(tmp_path / "ws")
        path = backend.prepare_workspace(iteration=99)
        expected = tmp_path / "ws" / "iter_0099"
        assert path == expected
        assert expected.is_dir()

    def test_iteration_1_parent_workspace_also_exists(self, tmp_path):
        """The parent workspace dir exists after prepare_workspace(iteration=1)."""
        backend = LocalProcessBackend(tmp_path / "ws")
        backend.prepare_workspace(iteration=1)
        assert (tmp_path / "ws").is_dir()

    def test_iteration_idempotent(self, tmp_path):
        """prepare_workspace(iteration=N) is safe to call twice."""
        backend = LocalProcessBackend(tmp_path / "ws")
        p1 = backend.prepare_workspace(iteration=5)
        p2 = backend.prepare_workspace(iteration=5)
        assert p1 == p2
        assert p1.is_dir()

    def test_different_iterations_different_dirs(self, tmp_path):
        """Iterations 1 and 2 produce different subdirectories."""
        backend = LocalProcessBackend(tmp_path / "ws")
        p1 = backend.prepare_workspace(iteration=1)
        p2 = backend.prepare_workspace(iteration=2)
        assert p1 != p2
        assert p1.is_dir()
        assert p2.is_dir()


# ---------------------------------------------------------------------------
# ContainerBackend: prepare_workspace with iteration
# ---------------------------------------------------------------------------

class TestContainerBackendIterationWorkspace:
    def _make_backend(self, tmp_path: Path) -> ContainerBackend:
        return ContainerBackend(
            image="python:3.11-slim",
            host_workspace=tmp_path / "host_ws",
            container_workspace="/sandbox/workspace",
        )

    def test_none_iteration_returns_container_workspace(self, tmp_path):
        """iteration=None returns the top-level container workspace (existing behavior)."""
        backend = self._make_backend(tmp_path)
        path = backend.prepare_workspace(iteration=None)
        assert path == Path("/sandbox/workspace")

    def test_no_arg_unchanged(self, tmp_path):
        """prepare_workspace() (no arg) still returns top-level container workspace."""
        backend = self._make_backend(tmp_path)
        path = backend.prepare_workspace()
        assert path == Path("/sandbox/workspace")

    def test_iteration_2_returns_container_iter_path(self, tmp_path):
        """iteration=2 returns /sandbox/workspace/iter_0002."""
        backend = self._make_backend(tmp_path)
        path = backend.prepare_workspace(iteration=2)
        assert path == Path("/sandbox/workspace/iter_0002")

    def test_iteration_2_creates_host_subdir(self, tmp_path):
        """iteration=2 creates host_workspace/iter_0002/ on the host."""
        backend = self._make_backend(tmp_path)
        backend.prepare_workspace(iteration=2)
        assert (tmp_path / "host_ws" / "iter_0002").is_dir()

    def test_iteration_format_zero_padded(self, tmp_path):
        """Iteration number is zero-padded to 4 digits."""
        backend = self._make_backend(tmp_path)
        path = backend.prepare_workspace(iteration=7)
        assert "iter_0007" in str(path)
