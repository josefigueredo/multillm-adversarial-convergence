"""MM14 Step 4 — doctor diagnostics for container execution readiness.

TDD tests written before implementation.

The doctor output must distinguish three container states:
1. container backend + Docker available  → "container backend ready; run_subprocess invokes docker run"
2. container backend + Docker unavailable → "not found on $PATH" / "RuntimeError"
3. local_process backend → unchanged from MM13 baseline
"""

from __future__ import annotations

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
from src.doctor import doctor_config_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    backend: str = "local_process",
    sandbox_mode: str = "tool_calls",
    image: str = "python:3.11-slim",
) -> ResearchConfig:
    container = ContainerBackendConfig(image=image)
    sandbox = SandboxConfig(mode=sandbox_mode, backend=backend, container=container)
    return ResearchConfig(
        topic="T",
        goal="G",
        dimensions=("A",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(max_iterations=1, backend="claude-cli"),
        security=SecurityConfig(tool_execution_mode="sandboxed", sandbox=sandbox),
    )


# ---------------------------------------------------------------------------
# container backend + Docker available
# ---------------------------------------------------------------------------

class TestDoctorContainerBackendReady:
    def test_ready_text_when_docker_available(self, tmp_path):
        """When Docker is on $PATH, doctor says 'container backend ready'."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=True):
            report = doctor_config_text(config)
        assert "container backend ready" in report.text

    def test_ready_mentions_run_subprocess(self, tmp_path):
        """The ready line mentions that run_subprocess invokes docker run."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=True):
            report = doctor_config_text(config)
        assert "docker run" in report.text

    def test_ready_no_availability_hedge(self, tmp_path):
        """When Docker is confirmed present, the 'depends on availability' hedge is absent."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=True):
            report = doctor_config_text(config)
        assert "actual runtime guarantees depend on availability" not in report.text

    def test_ready_env_shaping_no_availability_hedge(self, tmp_path):
        """Env-shaping line drops availability hedge when Docker is confirmed present."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=True):
            report = doctor_config_text(config)
        assert "actual runtime guarantees depend on backend availability" not in report.text


# ---------------------------------------------------------------------------
# container backend + Docker unavailable
# ---------------------------------------------------------------------------

class TestDoctorContainerBackendNotFound:
    def test_not_found_text_when_docker_missing(self, tmp_path):
        """When Docker is absent, doctor warns about $PATH or RuntimeError."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=False):
            report = doctor_config_text(config)
        # Must say either "not found on $PATH" or "RuntimeError"
        text = report.text
        assert ("not found on $PATH" in text) or ("RuntimeError" in text)

    def test_not_found_still_shows_backend_configured(self, tmp_path):
        """Even when Docker is absent, the line still mentions 'container backend'."""
        config = _make_config(backend="container")
        with patch("src.sandbox.backends.container.ContainerBackend.is_available", return_value=False):
            report = doctor_config_text(config)
        assert "container backend" in report.text


# ---------------------------------------------------------------------------
# local_process backend — unchanged
# ---------------------------------------------------------------------------

class TestDoctorLocalProcessUnchanged:
    def test_local_process_output_unchanged(self, tmp_path):
        """local_process doctor output is unaffected by MM14 Step 4 changes."""
        config = _make_config(backend="local_process")
        report = doctor_config_text(config)
        assert "local_process" in report.text
        # Must NOT include container-specific wording
        assert "docker run" not in report.text
        assert "container backend ready" not in report.text

    def test_local_process_no_is_available_call(self, tmp_path):
        """is_available() is NOT called for local_process backend."""
        config = _make_config(backend="local_process")
        with patch(
            "src.sandbox.backends.container.ContainerBackend.is_available",
            side_effect=AssertionError("should not be called for local_process"),
        ):
            # Should not raise
            report = doctor_config_text(config)
        assert "local_process" in report.text
