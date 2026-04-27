"""MM13 Step 2 — sandbox backend selection config tests.

TDD tests that verify:
- ContainerBackendConfig holds container-specific settings
- SandboxConfig gains a backend selector and container sub-config
- _parse_security_config handles the container: sub-mapping
- select_sandbox_backend() returns the correct backend for each mode/backend combo
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml


# ══════════════════════════════════════════════════════════════════════════════
# ContainerBackendConfig
# ══════════════════════════════════════════════════════════════════════════════

class TestContainerBackendConfigImportable:
    def test_importable_from_config(self):
        from src.config import ContainerBackendConfig
        assert ContainerBackendConfig is not None


class TestContainerBackendConfigDefaults:
    def test_has_default_image(self):
        from src.config import ContainerBackendConfig
        cfg = ContainerBackendConfig()
        assert isinstance(cfg.image, str)
        assert len(cfg.image) > 0

    def test_has_default_container_workspace(self):
        from src.config import ContainerBackendConfig
        cfg = ContainerBackendConfig()
        assert isinstance(cfg.container_workspace, str)
        assert cfg.container_workspace.startswith("/")

    def test_custom_image(self):
        from src.config import ContainerBackendConfig
        cfg = ContainerBackendConfig(image="ubuntu:22.04")
        assert cfg.image == "ubuntu:22.04"

    def test_custom_container_workspace(self):
        from src.config import ContainerBackendConfig
        cfg = ContainerBackendConfig(container_workspace="/work")
        assert cfg.container_workspace == "/work"

    def test_is_frozen(self):
        from src.config import ContainerBackendConfig
        cfg = ContainerBackendConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.image = "other"  # type: ignore[misc]


# ══════════════════════════════════════════════════════════════════════════════
# SandboxConfig — backend selector + container sub-config
# ══════════════════════════════════════════════════════════════════════════════

class TestSandboxConfigBackendField:
    def test_has_backend_field(self):
        from src.config import SandboxConfig
        cfg = SandboxConfig()
        assert hasattr(cfg, "backend")

    def test_default_backend_is_local_process(self):
        from src.config import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.backend == "local_process"

    def test_backend_can_be_container(self):
        from src.config import SandboxConfig
        cfg = SandboxConfig(backend="container")
        assert cfg.backend == "container"

    def test_has_container_sub_config(self):
        from src.config import SandboxConfig
        cfg = SandboxConfig()
        assert hasattr(cfg, "container")

    def test_container_sub_config_is_container_backend_config(self):
        from src.config import ContainerBackendConfig, SandboxConfig
        cfg = SandboxConfig()
        assert isinstance(cfg.container, ContainerBackendConfig)


# ══════════════════════════════════════════════════════════════════════════════
# YAML parsing — security.sandbox.backend + security.sandbox.container
# ══════════════════════════════════════════════════════════════════════════════

def _parse_yaml_security(yaml_str: str):
    """Helper: parse a security: block through the real config parser."""
    from src.config import _parse_security_config
    raw = yaml.safe_load(yaml_str)
    return _parse_security_config(raw.get("security", raw))


class TestSandboxBackendYAMLParsing:
    def test_default_backend_when_omitted(self):
        cfg = _parse_yaml_security("security:\n  sandbox:\n    mode: off\n")
        assert cfg.sandbox.backend == "local_process"

    def test_explicit_local_process_backend(self):
        cfg = _parse_yaml_security(
            "security:\n  sandbox:\n    mode: off\n    backend: local_process\n"
        )
        assert cfg.sandbox.backend == "local_process"

    def test_container_backend_selection(self):
        cfg = _parse_yaml_security(
            "security:\n  sandbox:\n    mode: tool_calls\n    backend: container\n"
        )
        assert cfg.sandbox.backend == "container"

    def test_invalid_backend_raises(self):
        from src.config import _parse_security_config
        with pytest.raises(ValueError, match="backend"):
            _parse_security_config(
                {"sandbox": {"mode": "off", "backend": "docker_swarm"}}
            )

    def test_relative_container_workspace_rejected_at_parse_time(self):
        from src.config import _parse_security_config
        with pytest.raises(ValueError, match="absolute"):
            _parse_security_config({
                "sandbox": {
                    "mode": "tool_calls",
                    "backend": "container",
                    "container": {"container_workspace": "relative/path"},
                }
            })

    def test_absolute_container_workspace_accepted_at_parse_time(self):
        cfg = _parse_yaml_security(
            "security:\n"
            "  sandbox:\n"
            "    mode: tool_calls\n"
            "    backend: container\n"
            "    container:\n"
            "      container_workspace: /abs/path\n"
        )
        assert cfg.sandbox.container.container_workspace == "/abs/path"

    def test_container_sub_config_defaults_when_omitted(self):
        cfg = _parse_yaml_security(
            "security:\n  sandbox:\n    mode: tool_calls\n    backend: container\n"
        )
        assert isinstance(cfg.sandbox.container.image, str)
        assert cfg.sandbox.container.container_workspace.startswith("/")

    def test_container_image_from_yaml(self):
        yaml_str = (
            "security:\n"
            "  sandbox:\n"
            "    mode: tool_calls\n"
            "    backend: container\n"
            "    container:\n"
            "      image: ubuntu:22.04\n"
        )
        cfg = _parse_yaml_security(yaml_str)
        assert cfg.sandbox.container.image == "ubuntu:22.04"

    def test_container_workspace_from_yaml(self):
        yaml_str = (
            "security:\n"
            "  sandbox:\n"
            "    mode: tool_calls\n"
            "    backend: container\n"
            "    container:\n"
            "      container_workspace: /custom/workspace\n"
        )
        cfg = _parse_yaml_security(yaml_str)
        assert cfg.sandbox.container.container_workspace == "/custom/workspace"


# ══════════════════════════════════════════════════════════════════════════════
# select_sandbox_backend() factory
# ══════════════════════════════════════════════════════════════════════════════

class TestSelectSandboxBackendImportable:
    def test_importable_from_sandbox(self):
        from src.sandbox import select_sandbox_backend
        assert callable(select_sandbox_backend)


class TestSelectSandboxBackendLocalProcess:
    def test_local_process_backend_by_default(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.local_process import LocalProcessBackend

        cfg = SandboxConfig()  # backend="local_process"
        backend = select_sandbox_backend(cfg, tmp_path)
        assert isinstance(backend, LocalProcessBackend)

    def test_explicit_local_process(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.local_process import LocalProcessBackend

        cfg = SandboxConfig(backend="local_process")
        backend = select_sandbox_backend(cfg, tmp_path)
        assert isinstance(backend, LocalProcessBackend)


class TestSelectSandboxBackendContainer:
    def test_container_backend_selected(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend
        from src.sandbox.backends.container import ContainerBackend

        cfg = SandboxConfig(backend="container")
        backend = select_sandbox_backend(cfg, tmp_path)
        assert isinstance(backend, ContainerBackend)

    def test_container_backend_uses_configured_image(self, tmp_path: Path):
        from src.config import ContainerBackendConfig, SandboxConfig
        from src.sandbox import select_sandbox_backend

        cfg = SandboxConfig(
            backend="container",
            container=ContainerBackendConfig(image="ubuntu:22.04"),
        )
        backend = select_sandbox_backend(cfg, tmp_path)
        assert backend.image == "ubuntu:22.04"

    def test_container_backend_uses_configured_workspace(self, tmp_path: Path):
        from src.config import ContainerBackendConfig, SandboxConfig
        from src.sandbox import select_sandbox_backend

        cfg = SandboxConfig(
            backend="container",
            container=ContainerBackendConfig(container_workspace="/my/workspace"),
        )
        backend = select_sandbox_backend(cfg, tmp_path)
        assert backend.container_workspace == "/my/workspace"

    def test_container_backend_host_workspace_under_output_dir(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend

        cfg = SandboxConfig(backend="container")
        backend = select_sandbox_backend(cfg, tmp_path)
        assert str(backend.host_workspace).startswith(str(tmp_path))

    def test_unknown_backend_raises(self, tmp_path: Path):
        from src.config import SandboxConfig
        from src.sandbox import select_sandbox_backend

        cfg = SandboxConfig(backend="container")
        # Bypass frozen dataclass to inject invalid backend for this test
        import dataclasses
        bad_cfg = dataclasses.replace(cfg, backend="unknown_backend")
        with pytest.raises(ValueError, match="backend"):
            select_sandbox_backend(bad_cfg, tmp_path)
