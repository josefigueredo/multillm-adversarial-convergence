"""MM13 Step 4 — diagnostics and docs backend-aware truthfulness tests.

TDD tests verifying that explain_config_text() and doctor_config_text()
describe the configured sandbox backend honestly, including:
- backend type (local_process vs container)
- container image and container workspace when backend=container
- isolation guarantee language matching the actual substrate
"""
from __future__ import annotations

import pytest

from src.config import (
    ContainerBackendConfig,
    ExecutionConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(backend: str = "local_process", sandbox_mode: str = "off",
                 container: ContainerBackendConfig | None = None) -> ResearchConfig:
    sandbox = SandboxConfig(
        mode=sandbox_mode,
        backend=backend,
        container=container or ContainerBackendConfig(),
    )
    return ResearchConfig(
        topic="T",
        goal="G",
        dimensions=("A",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(max_iterations=1, backend="claude-cli"),
        security=SecurityConfig(
            tool_execution_mode="sandboxed",
            sandbox=sandbox,
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# explain_config_text — sandbox.backend field
# ══════════════════════════════════════════════════════════════════════════════

class TestExplainConfigSandboxBackend:
    def test_shows_local_process_backend_by_default(self):
        from src.explain import explain_config_text
        result = explain_config_text(_make_config("local_process"))
        assert "sandbox.backend" in result
        assert "local_process" in result

    def test_shows_container_backend_when_configured(self):
        from src.explain import explain_config_text
        result = explain_config_text(_make_config("container"))
        assert "sandbox.backend" in result
        assert "container" in result

    def test_shows_container_image_when_configured(self):
        from src.explain import explain_config_text
        cfg = _make_config("container", container=ContainerBackendConfig(image="ubuntu:22.04"))
        result = explain_config_text(cfg)
        assert "ubuntu:22.04" in result

    def test_shows_container_workspace_when_configured(self):
        from src.explain import explain_config_text
        cfg = _make_config("container", container=ContainerBackendConfig(container_workspace="/work"))
        result = explain_config_text(cfg)
        assert "/work" in result

    def test_no_container_image_shown_for_local_process(self):
        from src.explain import explain_config_text
        result = explain_config_text(_make_config("local_process"))
        # Should not surface container-specific details for local_process
        assert "python:3.11-slim" not in result


# ══════════════════════════════════════════════════════════════════════════════
# doctor_config_text — backend type section
# ══════════════════════════════════════════════════════════════════════════════

class TestDoctorConfigSandboxBackend:
    def test_local_process_backend_described_accurately(self):
        from src.doctor import doctor_config_text
        cfg = _make_config("local_process", sandbox_mode="tool_calls")
        report = doctor_config_text(cfg)
        text = report.text
        assert "local_process" in text or "local-process" in text

    def test_container_backend_type_shown_in_doctor(self):
        from src.doctor import doctor_config_text
        cfg = _make_config("container", sandbox_mode="tool_calls")
        report = doctor_config_text(cfg)
        text = report.text
        assert "container" in text

    def test_container_image_shown_in_doctor(self):
        from src.doctor import doctor_config_text
        cfg = _make_config(
            "container", sandbox_mode="tool_calls",
            container=ContainerBackendConfig(image="ubuntu:22.04"),
        )
        report = doctor_config_text(cfg)
        assert "ubuntu:22.04" in report.text

    def test_container_isolation_language_differs_from_local(self):
        """Container backend must not claim process-level; must be honest about guarantees."""
        from src.doctor import doctor_config_text
        local_report = doctor_config_text(_make_config("local_process", sandbox_mode="tool_calls"))
        container_report = doctor_config_text(_make_config("container", sandbox_mode="tool_calls"))
        # local_process says process-level
        assert "process-level" in local_report.text
        # container mentions "container backend" in some form (ready, configured, or not found)
        assert "container backend" in container_report.text
        # container does not claim process-level isolation
        sandbox_lines = [
            l for l in container_report.text.splitlines()
            if "sandbox backend" in l.lower()
        ]
        for line in sandbox_lines:
            assert "process-level" not in line

    def test_doctor_sandbox_backend_section_not_always_local(self):
        """Verifies we no longer hard-code 'local-process' for all backends."""
        from src.doctor import doctor_config_text
        cfg = _make_config("container", sandbox_mode="tool_calls",
                           container=ContainerBackendConfig(image="alpine:3.18"))
        report = doctor_config_text(cfg)
        # The old hard-coded text was: "local-process  (LocalProcessBackend — process-level isolation)"
        # It should no longer appear when backend=container
        lines_with_backend = [
            line for line in report.text.splitlines()
            if "sandbox backend" in line.lower()
        ]
        assert lines_with_backend, "No sandbox backend line found in doctor output"
        # None of those lines should hard-code local-process when container is configured
        for line in lines_with_backend:
            assert "LocalProcessBackend" not in line, (
                f"Doctor still hard-codes LocalProcessBackend for container config: {line!r}"
            )
