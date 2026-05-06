"""Orchestrator backend selection integration tests.

TDD tests that verify:
- _setup_run() injects ContainerBackend when backend=container is configured
- _setup_run() injects LocalProcessBackend when backend=local_process (default)
- _make_transient_sandbox() also respects the configured backend
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import (
    ContainerBackendConfig,
    ExecutionConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)
from src.sandbox.backends.container import ContainerBackend
from src.sandbox.backends.local_process import LocalProcessBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(backend: str = "local_process", container: ContainerBackendConfig | None = None) -> ResearchConfig:
    sandbox = SandboxConfig(
        backend=backend,
        container=container or ContainerBackendConfig(),
    )
    return ResearchConfig(
        topic="T",
        goal="G",
        dimensions=("A",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            max_iterations=1,
            backend="claude-cli",
            timeout_seconds=5,
        ),
        security=SecurityConfig(sandbox=sandbox),
    )


def _make_researcher(config: ResearchConfig, tmp_path: Path):
    """Create an AutoResearcher with a fake backend."""
    from tests.test_orchestrator import FakeBackend  # reuse existing stub

    from src.orchestrator import AutoResearcher

    fake = FakeBackend()
    return AutoResearcher(config=config, backend=fake, output_dir=tmp_path / "output")


_SETUP_PATCHES = (
    patch("src.orchestrator.git_commit", return_value="abc123"),
    patch("src.orchestrator.cli_version", return_value="1.0"),
    patch("src.orchestrator.package_version", return_value="0.2.0"),
)


def _run_setup(researcher) -> None:
    with _SETUP_PATCHES[0], _SETUP_PATCHES[1], _SETUP_PATCHES[2]:
        researcher._setup()


# ══════════════════════════════════════════════════════════════════════════════
# _setup_run — backend injection
# ══════════════════════════════════════════════════════════════════════════════

class TestSetupRunBackendSelection:
    def test_default_backend_is_local_process(self, tmp_path):
        researcher = _make_researcher(_make_config("local_process"), tmp_path)
        _run_setup(researcher)
        assert isinstance(researcher._sandbox._backend, LocalProcessBackend)

    def test_container_config_injects_container_backend(self, tmp_path):
        researcher = _make_researcher(_make_config("container"), tmp_path)
        _run_setup(researcher)
        assert isinstance(researcher._sandbox._backend, ContainerBackend)

    def test_container_backend_image_matches_config(self, tmp_path):
        cfg = _make_config("container", ContainerBackendConfig(image="ubuntu:22.04"))
        researcher = _make_researcher(cfg, tmp_path)
        _run_setup(researcher)
        assert researcher._sandbox._backend.image == "ubuntu:22.04"

    def test_container_backend_workspace_matches_config(self, tmp_path):
        cfg = _make_config("container", ContainerBackendConfig(container_workspace="/work"))
        researcher = _make_researcher(cfg, tmp_path)
        _run_setup(researcher)
        backend = researcher._sandbox._backend
        assert isinstance(backend, ContainerBackend)
        assert backend.container_workspace == "/work"


# ══════════════════════════════════════════════════════════════════════════════
# _make_transient_sandbox — backend injection
# ══════════════════════════════════════════════════════════════════════════════

class TestTransientSandboxBackendSelection:
    def test_transient_default_is_local_process(self, tmp_path):
        researcher = _make_researcher(_make_config("local_process"), tmp_path)
        sandbox = researcher._make_transient_sandbox()
        assert isinstance(sandbox._backend, LocalProcessBackend)

    def test_transient_container_config_injects_container_backend(self, tmp_path):
        researcher = _make_researcher(_make_config("container"), tmp_path)
        sandbox = researcher._make_transient_sandbox()
        assert isinstance(sandbox._backend, ContainerBackend)

    def test_transient_container_image_matches_config(self, tmp_path):
        cfg = _make_config("container", ContainerBackendConfig(image="alpine:3.18"))
        researcher = _make_researcher(cfg, tmp_path)
        sandbox = researcher._make_transient_sandbox()
        assert sandbox._backend.image == "alpine:3.18"
