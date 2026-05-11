"""Container sandbox backend scaffold tests.

TDD tests that verify:
- ContainerBackend implements SandboxBackend interface
- prepare_workspace() creates and returns the host workspace path
- build_environment() returns a minimal sanitized env dict
- is_available() returns a bool without requiring Docker to be installed
- Importable without Docker present
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestContainerBackendContract:
    """Type-system / class-shape invariants — collapsed from five separate
    classes (Importable, Inheritance, Construction) that each tested a
    single trivial property. Behaviour tests live in the dedicated
    PrepareWorkspace / BuildEnvironment / Availability / Validation
    classes below."""

    def test_is_a_sandbox_backend(self):
        from src.sandbox.backends.base import SandboxBackend
        from src.sandbox.backends.container import ContainerBackend
        assert issubclass(ContainerBackend, SandboxBackend)
        assert callable(ContainerBackend.prepare_workspace)
        assert callable(ContainerBackend.build_environment)

    def test_construction_stores_fields(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        # Default container_workspace path
        default = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        assert default.image == "python:3.11-slim"
        assert default.host_workspace == tmp_path
        assert isinstance(default.container_workspace, str)
        assert default.container_workspace  # non-empty default
        # Explicit container_workspace override
        custom = ContainerBackend(
            image="python:3.11-slim",
            host_workspace=tmp_path,
            container_workspace="/sandbox/work",
        )
        assert custom.container_workspace == "/sandbox/work"


class TestContainerBackendPrepareWorkspace:
    def test_returns_path(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        result = backend.prepare_workspace()
        assert isinstance(result, Path)

    def test_creates_host_workspace_dir(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        assert not ws.exists()
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        backend.prepare_workspace()
        assert ws.exists()

    def test_idempotent(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        backend.prepare_workspace()
        backend.prepare_workspace()  # second call must not raise
        assert ws.exists()

    def test_returns_container_workspace_path(self, tmp_path: Path):
        """Returned path is the authoritative container-side execution path."""
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        result = backend.prepare_workspace()
        assert result == Path(backend.container_workspace)

    def test_returns_default_container_workspace(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        result = backend.prepare_workspace()
        assert result == Path("/sandbox/workspace")

    def test_custom_container_workspace_is_returned(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(
            image="python:3.11-slim",
            host_workspace=ws,
            container_workspace="/custom/exec",
        )
        result = backend.prepare_workspace()
        assert result == Path("/custom/exec")

    def test_host_dir_created_even_with_custom_container_path(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(
            image="python:3.11-slim",
            host_workspace=ws,
            container_workspace="/custom/exec",
        )
        backend.prepare_workspace()
        assert ws.exists()

    def test_returned_path_is_not_host_path(self, tmp_path: Path):
        """Container backend must NOT return the host-side path."""
        from src.sandbox.backends.container import ContainerBackend
        ws = tmp_path / "workspace"
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=ws)
        result = backend.prepare_workspace()
        assert result != ws


class TestContainerBackendBuildEnvironment:
    def test_returns_dict(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        env = backend.build_environment()
        assert isinstance(env, dict)

    def test_all_values_are_strings(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        env = backend.build_environment()
        for k, v in env.items():
            assert isinstance(k, str), f"Key {k!r} is not a string"
            assert isinstance(v, str), f"Value for {k!r} is not a string"

    def test_uses_base_env_when_provided(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        base = {"PATH": "/usr/bin", "HOME": "/root"}
        env = backend.build_environment(base_env=base)
        assert isinstance(env, dict)

    def test_does_not_mutate_base_env(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        base = {"PATH": "/usr/bin", "SECRET": "hidden"}
        original = dict(base)
        backend.build_environment(base_env=base)
        assert base == original

    def test_strips_secrets_from_env(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        backend = ContainerBackend(image="python:3.11-slim", host_workspace=tmp_path)
        base = {
            "PATH": "/usr/bin",
            "AWS_SECRET_ACCESS_KEY": "secret123",
            "ANTHROPIC_API_KEY": "sk-secret",
        }
        env = backend.build_environment(base_env=base)
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "ANTHROPIC_API_KEY" not in env


class TestContainerBackendAvailability:
    def test_is_available_returns_bool(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        result = ContainerBackend.is_available()
        assert isinstance(result, bool)

    def test_is_available_true_when_docker_present(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        with patch("shutil.which", return_value="/usr/bin/docker"):
            assert ContainerBackend.is_available() is True

    def test_is_available_false_when_docker_absent(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        with patch("shutil.which", return_value=None):
            assert ContainerBackend.is_available() is False

    def test_no_import_error_without_docker(self):
        # Importing ContainerBackend must not raise even if docker is not installed
        with patch("shutil.which", return_value=None):
            from src.sandbox.backends.container import ContainerBackend  # noqa: F401


class TestContainerBackendValidation:
    def test_relative_container_workspace_raises(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        with pytest.raises(ValueError, match="absolute"):
            ContainerBackend(
                image="python:3.11-slim",
                host_workspace=tmp_path,
                container_workspace="relative/path",
            )

    def test_no_leading_slash_raises(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        with pytest.raises(ValueError):
            ContainerBackend(
                image="python:3.11-slim",
                host_workspace=tmp_path,
                container_workspace="sandbox/work",
            )

    def test_absolute_path_accepted(self, tmp_path: Path):
        from src.sandbox.backends.container import ContainerBackend
        # Must not raise
        backend = ContainerBackend(
            image="python:3.11-slim",
            host_workspace=tmp_path,
            container_workspace="/valid/abs/path",
        )
        assert backend.container_workspace == "/valid/abs/path"


class TestContainerBackendSandboxPackageExport:
    def test_sandbox_init_exposes_container_backend(self):
        from src.sandbox import ContainerBackend
        assert ContainerBackend is not None

    def test_sandbox_init_still_exposes_local_process(self):
        from src.sandbox import LocalProcessBackend
        assert LocalProcessBackend is not None

    def test_backends_package_exposes_container_backend(self):
        from src.sandbox.backends import ContainerBackend
        assert ContainerBackend is not None
