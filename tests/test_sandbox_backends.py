"""Tests for src.sandbox.backends — sandbox backend seam."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.sandbox.backends.base import SandboxBackend
from src.sandbox.backends.local_process import LocalProcessBackend
from src.policy.sandbox_executor import SandboxExecutor
from src.policy.security_runtime import RuntimeSecurityPolicy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(tmp_path: Path) -> RuntimeSecurityPolicy:
    output_dir = tmp_path / "output"
    workspace_dir = output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode="sandboxed",
        sandbox_active=True,
        _allow_host_bash=False,
        _allow_filesystem_write_outside_output=False,
        _filesystem_access="output_only",
        _network_access="unrestricted",
        output_dir=output_dir,
        workspace_dir=workspace_dir,
    )


def _make_executor(tmp_path: Path, **kwargs) -> SandboxExecutor:
    policy = _make_policy(tmp_path)
    workspace_dir = tmp_path / "output" / ".workspace"
    return SandboxExecutor(policy, workspace_dir, **kwargs)


# ---------------------------------------------------------------------------
# SandboxBackend ABC contract
# ---------------------------------------------------------------------------

class TestSandboxBackendABC:
    def test_is_abstract(self):
        """SandboxBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            SandboxBackend()  # type: ignore[abstract]

    def test_has_prepare_workspace(self):
        assert hasattr(SandboxBackend, "prepare_workspace")

    def test_has_build_environment(self):
        assert hasattr(SandboxBackend, "build_environment")


# ---------------------------------------------------------------------------
# LocalProcessBackend
# ---------------------------------------------------------------------------

class TestLocalProcessBackend:
    def test_prepare_workspace_creates_directory(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        assert not ws.exists()
        backend.prepare_workspace()
        assert ws.is_dir()

    def test_prepare_workspace_returns_workspace_path(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        result = backend.prepare_workspace()
        assert result == ws

    def test_prepare_workspace_is_idempotent(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        backend.prepare_workspace()
        backend.prepare_workspace()  # must not raise
        assert ws.is_dir()

    def test_prepare_workspace_creates_parents(self, tmp_path):
        ws = tmp_path / "a" / "b" / ".workspace"
        backend = LocalProcessBackend(ws)
        backend.prepare_workspace()
        assert ws.is_dir()

    def test_build_environment_preserves_allowlisted_keys(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        base = {"PATH": "/usr/bin", "HOME": "/home/user", "ANTHROPIC_API_KEY": "sk-abc"}
        result = backend.build_environment(base)
        assert result["PATH"] == "/usr/bin"
        assert result["HOME"] == "/home/user"
        assert result["ANTHROPIC_API_KEY"] == "sk-abc"

    def test_build_environment_strips_sensitive_keys(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        base = {
            "PATH": "/usr/bin",
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "HISTFILE": "/home/user/.bash_history",
            "CI": "true",
            "GITHUB_ACTIONS": "true",
        }
        result = backend.build_environment(base)
        assert "SSH_AUTH_SOCK" not in result
        assert "HISTFILE" not in result
        assert "CI" not in result
        assert "GITHUB_ACTIONS" not in result
        assert "PATH" in result

    def test_build_environment_uses_os_environ_when_none(self, tmp_path, monkeypatch):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        monkeypatch.setenv("PATH", "/test/path")
        result = backend.build_environment(None)
        assert "PATH" in result

    def test_build_environment_does_not_mutate_source(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        base = {"PATH": "/usr/bin", "SECRET": "value"}
        original = dict(base)
        backend.build_environment(base)
        assert base == original

    def test_build_environment_case_insensitive_matching(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        base = {"path": "/usr/bin", "home": "/home/user"}
        result = backend.build_environment(base)
        assert "path" in result
        assert "home" in result

    def test_is_sandbox_backend_subclass(self, tmp_path):
        ws = tmp_path / ".workspace"
        backend = LocalProcessBackend(ws)
        assert isinstance(backend, SandboxBackend)


# ---------------------------------------------------------------------------
# SandboxExecutor delegation to backend
# ---------------------------------------------------------------------------

class TestSandboxExecutorBackendDelegation:
    def test_uses_local_process_backend_by_default(self, tmp_path):
        executor = _make_executor(tmp_path)
        assert isinstance(executor._backend, LocalProcessBackend)

    def test_accepts_custom_backend(self, tmp_path):
        ws = tmp_path / "output" / ".workspace"
        custom = MagicMock(spec=SandboxBackend)
        custom.prepare_workspace.return_value = ws
        custom.build_environment.return_value = {"PATH": "/custom"}
        executor = _make_executor(tmp_path, backend=custom)
        assert executor._backend is custom

    def test_prepare_workspace_delegates_to_backend(self, tmp_path):
        ws = tmp_path / "output" / ".workspace"
        mock_backend = MagicMock(spec=SandboxBackend)
        mock_backend.prepare_workspace.return_value = ws
        executor = _make_executor(tmp_path, backend=mock_backend)
        result = executor.prepare_workspace()
        mock_backend.prepare_workspace.assert_called_once()
        assert result == ws

    def test_prepare_workspace_updates_workspace_dir(self, tmp_path):
        """Executor workspace_dir reflects path returned by backend (supports container override)."""
        ws = tmp_path / "container" / "mount"
        mock_backend = MagicMock(spec=SandboxBackend)
        mock_backend.prepare_workspace.return_value = ws
        executor = _make_executor(tmp_path, backend=mock_backend)
        executor.prepare_workspace()
        assert executor.workspace_dir == ws

    def test_build_environment_delegates_to_backend(self, tmp_path):
        mock_backend = MagicMock(spec=SandboxBackend)
        mock_backend.build_environment.return_value = {"PATH": "/delegated"}
        executor = _make_executor(tmp_path, backend=mock_backend)
        base = {"PATH": "/usr/bin"}
        result = executor.build_environment(base)
        mock_backend.build_environment.assert_called_once_with(base)
        assert result == {"PATH": "/delegated"}

    def test_external_behavior_unchanged_prepare_workspace(self, tmp_path):
        """With default backend, prepare_workspace still creates the real directory."""
        executor = _make_executor(tmp_path)
        ws = executor.workspace_dir
        assert not ws.exists()
        executor.prepare_workspace()
        assert ws.is_dir()

    def test_external_behavior_unchanged_build_environment(self, tmp_path):
        """With default backend, build_environment still filters the allowlist."""
        executor = _make_executor(tmp_path)
        base = {"PATH": "/usr/bin", "HOME": "/home/user", "HISTFILE": "/h"}
        result = executor.build_environment(base)
        assert "PATH" in result
        assert "HOME" in result
        assert "HISTFILE" not in result


# ---------------------------------------------------------------------------
# SandboxEnvPolicy
# ---------------------------------------------------------------------------

from src.sandbox.backends.local_process import (
    SandboxEnvPolicy,
    _REQUIRED_ENV_VARS,
    _OPTIONAL_ENV_VARS,
    _DENIED_ENV_VARS,
)


class TestSandboxEnvPolicy:
    def test_is_frozen(self):
        policy = SandboxEnvPolicy()
        with pytest.raises((AttributeError, TypeError)):
            policy.include_optional = False  # type: ignore[misc]

    def test_default_include_optional_is_true(self):
        assert SandboxEnvPolicy().include_optional is True

    def test_effective_allowlist_includes_required_when_optional_true(self):
        policy = SandboxEnvPolicy(include_optional=True)
        allowlist = policy.effective_allowlist()
        assert "PATH" in allowlist
        assert "HOME" in allowlist

    def test_effective_allowlist_includes_required_when_optional_false(self):
        policy = SandboxEnvPolicy(include_optional=False)
        allowlist = policy.effective_allowlist()
        assert "PATH" in allowlist
        assert "HOME" in allowlist

    def test_effective_allowlist_includes_optional_when_true(self):
        policy = SandboxEnvPolicy(include_optional=True)
        allowlist = policy.effective_allowlist()
        assert "ANTHROPIC_API_KEY" in allowlist
        assert "HTTP_PROXY" in allowlist

    def test_effective_allowlist_excludes_optional_when_false(self):
        policy = SandboxEnvPolicy(include_optional=False)
        allowlist = policy.effective_allowlist()
        assert "ANTHROPIC_API_KEY" not in allowlist
        assert "HTTP_PROXY" not in allowlist

    def test_denied_vars_never_in_effective_allowlist(self):
        policy = SandboxEnvPolicy(include_optional=True)
        allowlist = policy.effective_allowlist()
        for name in ("SSH_AUTH_SOCK", "HISTFILE", "CI", "GITHUB_ACTIONS"):
            assert name not in allowlist, f"{name!r} should be denied"

    def test_denied_wins_over_custom_required(self):
        """If a var appears in both required and denied, denied must win."""
        custom_policy = SandboxEnvPolicy(
            required_vars=frozenset({"SSH_AUTH_SOCK"}),
            optional_vars=frozenset(),
            denied_vars=frozenset({"SSH_AUTH_SOCK"}),
            include_optional=True,
        )
        assert "SSH_AUTH_SOCK" not in custom_policy.effective_allowlist()

    def test_denied_wins_over_custom_optional(self):
        """If a var appears in both optional and denied, denied must win."""
        custom_policy = SandboxEnvPolicy(
            required_vars=frozenset(),
            optional_vars=frozenset({"CI"}),
            denied_vars=frozenset({"CI"}),
            include_optional=True,
        )
        assert "CI" not in custom_policy.effective_allowlist()

    def test_strategy_summary_contains_expected_keys(self):
        summary = SandboxEnvPolicy().strategy_summary()
        assert "required" in summary
        assert "optional" in summary
        assert "optional_active" in summary
        assert "denied" in summary
        assert "effective" in summary

    def test_strategy_summary_optional_active_reflects_flag(self):
        assert SandboxEnvPolicy(include_optional=True).strategy_summary()["optional_active"] is True
        assert SandboxEnvPolicy(include_optional=False).strategy_summary()["optional_active"] is False

    def test_strategy_summary_effective_count_matches_allowlist(self):
        policy = SandboxEnvPolicy()
        summary = policy.strategy_summary()
        assert summary["effective"] == len(policy.effective_allowlist())

    def test_aws_vars_in_optional(self):
        policy = SandboxEnvPolicy(include_optional=True)
        allowlist = policy.effective_allowlist()
        for name in ("AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID",
                     "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            assert name in allowlist, f"{name!r} should be in optional vars"

    def test_litellm_vars_in_optional(self):
        policy = SandboxEnvPolicy(include_optional=True)
        allowlist = policy.effective_allowlist()
        assert "LITELLM_API_KEY" in allowlist
        assert "LITELLM_BASE_URL" in allowlist

    def test_aws_and_litellm_excluded_when_optional_false(self):
        policy = SandboxEnvPolicy(include_optional=False)
        allowlist = policy.effective_allowlist()
        for name in ("AWS_REGION", "AWS_ACCESS_KEY_ID", "LITELLM_API_KEY"):
            assert name not in allowlist


class TestEnvVarCategoryInvariants:
    def test_default_denied_not_in_required(self):
        overlap = _DENIED_ENV_VARS & _REQUIRED_ENV_VARS
        assert overlap == frozenset(), f"Vars in both denied and required: {overlap}"

    def test_default_denied_not_in_optional(self):
        overlap = _DENIED_ENV_VARS & _OPTIONAL_ENV_VARS
        assert overlap == frozenset(), f"Vars in both denied and optional: {overlap}"

    def test_required_and_optional_dont_overlap(self):
        overlap = _REQUIRED_ENV_VARS & _OPTIONAL_ENV_VARS
        assert overlap == frozenset(), f"Vars in both required and optional: {overlap}"


class TestLocalProcessBackendWithPolicy:
    def test_default_policy_preserves_required_vars(self, tmp_path):
        backend = LocalProcessBackend(tmp_path / "ws")
        result = backend.build_environment({"PATH": "/usr/bin", "HOME": "/home"})
        assert "PATH" in result
        assert "HOME" in result

    def test_default_policy_includes_api_keys(self, tmp_path):
        backend = LocalProcessBackend(tmp_path / "ws")
        result = backend.build_environment({"ANTHROPIC_API_KEY": "sk-abc"})
        assert result.get("ANTHROPIC_API_KEY") == "sk-abc"

    def test_custom_policy_excludes_api_keys_when_optional_off(self, tmp_path):
        policy = SandboxEnvPolicy(include_optional=False)
        backend = LocalProcessBackend(tmp_path / "ws", policy=policy)
        result = backend.build_environment({
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-abc",
            "LITELLM_API_KEY": "lit-key",
        })
        assert "PATH" in result
        assert "ANTHROPIC_API_KEY" not in result
        assert "LITELLM_API_KEY" not in result

    def test_denied_vars_stripped_regardless_of_policy(self, tmp_path):
        backend = LocalProcessBackend(tmp_path / "ws")
        result = backend.build_environment({
            "PATH": "/usr/bin",
            "SSH_AUTH_SOCK": "/tmp/agent.sock",
            "CI": "true",
        })
        assert "SSH_AUTH_SOCK" not in result
        assert "CI" not in result

    def test_backend_exposes_policy_property(self, tmp_path):
        policy = SandboxEnvPolicy(include_optional=False)
        backend = LocalProcessBackend(tmp_path / "ws", policy=policy)
        assert backend.policy is policy

    def test_default_backend_has_default_policy(self, tmp_path):
        backend = LocalProcessBackend(tmp_path / "ws")
        assert isinstance(backend.policy, SandboxEnvPolicy)
        assert backend.policy.include_optional is True
