"""MM13 Step 5 — container backend unavailability fallback tests.

TDD tests verifying that select_sandbox_backend() raises a clear, actionable
error when the container backend is configured but Docker is not available,
rather than silently succeeding or producing a confusing downstream error.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import ContainerBackendConfig, SandboxConfig


def _container_sandbox_config(image: str = "python:3.11-slim") -> SandboxConfig:
    return SandboxConfig(
        backend="container",
        container=ContainerBackendConfig(image=image),
    )


def _local_sandbox_config() -> SandboxConfig:
    return SandboxConfig(backend="local_process")


# ══════════════════════════════════════════════════════════════════════════════
# select_sandbox_backend — container unavailable
# ══════════════════════════════════════════════════════════════════════════════

class TestContainerUnavailableFallback:
    def test_raises_when_docker_not_on_path(self, tmp_path):
        from src.sandbox import select_sandbox_backend
        with patch("src.sandbox.backends.container.shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                select_sandbox_backend(_container_sandbox_config(), tmp_path)
        assert "docker" in str(exc_info.value).lower()

    def test_error_message_mentions_configured_backend(self, tmp_path):
        from src.sandbox import select_sandbox_backend
        with patch("src.sandbox.backends.container.shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                select_sandbox_backend(_container_sandbox_config(), tmp_path)
        assert "container" in str(exc_info.value).lower()

    def test_error_message_suggests_remediation(self, tmp_path):
        """The error should tell the operator how to fix it."""
        from src.sandbox import select_sandbox_backend
        with patch("src.sandbox.backends.container.shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                select_sandbox_backend(_container_sandbox_config(), tmp_path)
        msg = str(exc_info.value).lower()
        # Should suggest switching to local_process or installing docker
        assert "local_process" in msg or "install" in msg

    def test_local_process_backend_ignores_docker_availability(self, tmp_path):
        """local_process must not check for Docker."""
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.local_process import LocalProcessBackend
        with patch("src.sandbox.backends.container.shutil.which", return_value=None):
            backend = select_sandbox_backend(_local_sandbox_config(), tmp_path)
        assert isinstance(backend, LocalProcessBackend)

    def test_container_backend_succeeds_when_docker_available(self, tmp_path):
        """When Docker is present, no error should be raised."""
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.container import ContainerBackend
        with patch("src.sandbox.backends.container.shutil.which", return_value="/usr/bin/docker"):
            backend = select_sandbox_backend(_container_sandbox_config(), tmp_path)
        assert isinstance(backend, ContainerBackend)


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator — propagates clear error on container unavailable
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorContainerUnavailable:
    """The RuntimeError from select_sandbox_backend must surface cleanly from _setup_run."""

    def _make_researcher(self, tmp_path: Path):
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        from src.config import (
            ExecutionConfig, ResearchConfig, ScoringConfig, SecurityConfig,
        )
        cfg = ResearchConfig(
            topic="T", goal="G", dimensions=("A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(max_iterations=1, backend="claude-cli"),
            security=SecurityConfig(
                sandbox=SandboxConfig(
                    backend="container",
                    container=ContainerBackendConfig(),
                ),
            ),
        )
        return AutoResearcher(config=cfg, backend=FakeBackend(), output_dir=tmp_path / "out")

    def test_setup_raises_when_docker_unavailable(self, tmp_path):
        researcher = self._make_researcher(tmp_path)
        with patch("src.sandbox.backends.container.shutil.which", return_value=None), \
             patch("src.orchestrator.git_commit", return_value="abc"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.1"):
            with pytest.raises(RuntimeError) as exc_info:
                researcher._setup()
        assert "docker" in str(exc_info.value).lower()
