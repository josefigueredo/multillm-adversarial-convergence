"""Tests for src.sandbox_executor — SandboxExecutor abstraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.policy.sandbox_executor import SandboxExecutor
from src.policy.security_runtime import RuntimeSecurityPolicy
from src.policy.policy_denial import PolicyDeniedError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_policy(
    tmp_path: Path,
    *,
    tool_execution_mode: str = "direct",
    filesystem_access: str = "output_only",
    network_access: str = "unrestricted",
    allow_host_bash: bool = True,
    allow_filesystem_write_outside_output: bool = False,
    sandbox_active: bool = False,
) -> RuntimeSecurityPolicy:
    output_dir = tmp_path / "output"
    workspace_dir = output_dir / ".workspace"
    return RuntimeSecurityPolicy(
        tool_execution_mode=tool_execution_mode,
        sandbox_active=sandbox_active,
        _allow_host_bash=allow_host_bash,
        _allow_filesystem_write_outside_output=allow_filesystem_write_outside_output,
        _filesystem_access=filesystem_access,
        _network_access=network_access,
        output_dir=output_dir,
        workspace_dir=workspace_dir,
    )


def _make_executor(
    tmp_path: Path, *, sandbox_active: bool = False, **kwargs
) -> SandboxExecutor:
    policy = _make_policy(tmp_path, sandbox_active=sandbox_active, **kwargs)
    return SandboxExecutor(policy, policy.workspace_dir)


# ---------------------------------------------------------------------------
# Construction — no side effects
# ---------------------------------------------------------------------------

class TestSandboxExecutorConstruction:
    def test_can_be_constructed_from_policy(self, tmp_path):
        executor = _make_executor(tmp_path)
        assert executor is not None

    def test_no_filesystem_side_effects_on_construction(self, tmp_path):
        """Construction must not create workspace or any directory."""
        executor = _make_executor(tmp_path)
        workspace = executor.workspace_dir
        assert not workspace.exists(), (
            f"Construction must not create {workspace}"
        )

    def test_workspace_dir_is_execution_root(self, tmp_path):
        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.workspace_dir == policy.workspace_dir

    def test_policy_is_accessible(self, tmp_path):
        policy = _make_policy(tmp_path)
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.policy is policy

    def test_allowed_write_roots_come_from_policy(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="output_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.allowed_write_roots() == policy.allowed_write_roots()

    def test_allowed_write_roots_workspace_only(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="workspace_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.allowed_write_roots() == [policy.workspace_dir]

    def test_network_mode_comes_from_policy(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="web_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.network_mode() == "web_only"

    def test_network_mode_none(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="none")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.network_mode() == "none"

    def test_network_mode_unrestricted(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        assert executor.network_mode() == "unrestricted"


# ---------------------------------------------------------------------------
# prepare_workspace — creates directory
# ---------------------------------------------------------------------------

class TestPrepareWorkspace:
    def test_creates_workspace_dir(self, tmp_path):
        executor = _make_executor(tmp_path)
        workspace = executor.workspace_dir
        assert not workspace.exists()
        executor.prepare_workspace()
        assert workspace.exists()
        assert workspace.is_dir()

    def test_idempotent_if_already_exists(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor.prepare_workspace()
        executor.prepare_workspace()  # must not raise
        assert executor.workspace_dir.is_dir()

    def test_returns_workspace_path(self, tmp_path):
        executor = _make_executor(tmp_path)
        result = executor.prepare_workspace()
        assert result == executor.workspace_dir


# ---------------------------------------------------------------------------
# validate_tool_request — filesystem checks
# ---------------------------------------------------------------------------

class TestValidateToolRequestFilesystem:
    def test_write_inside_output_dir_allowed(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="output_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        inside = policy.output_dir / "some_file.txt"
        # Must not raise
        executor.validate_tool_request(action="write_file", write_path=inside)

    def test_write_inside_workspace_allowed_workspace_only(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="workspace_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        inside = policy.workspace_dir / "file.txt"
        executor.validate_tool_request(action="write_file", write_path=inside)

    def test_write_outside_output_dir_denied(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="output_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        outside = tmp_path / "outside.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="write_file", write_path=outside)
        err = exc_info.value
        assert err.reason_code == "write_outside_allowed_roots"
        assert err.policy_field == "sandbox.filesystem_access"
        assert err.requested_action == "write_file"

    def test_write_at_output_root_denied_workspace_only(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="workspace_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        output_root_file = policy.output_dir / "file.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="write_file", write_path=output_root_file)
        assert exc_info.value.reason_code == "write_outside_allowed_roots"

    def test_broad_write_flag_allows_outside_path(self, tmp_path):
        policy = _make_policy(
            tmp_path,
            filesystem_access="output_only",
            allow_filesystem_write_outside_output=True,
        )
        executor = SandboxExecutor(policy, policy.workspace_dir)
        outside = tmp_path / "anywhere.txt"
        executor.validate_tool_request(action="write_file", write_path=outside)

    def test_no_write_path_does_not_raise(self, tmp_path):
        executor = _make_executor(tmp_path)
        executor.validate_tool_request(action="read_file")

    def test_error_carries_allowed_boundary(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="output_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        outside = tmp_path / "outside.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="write_file", write_path=outside)
        assert exc_info.value.allowed_boundary == "output_only"

    def test_error_carries_workspace_only_boundary_token(self, tmp_path):
        policy = _make_policy(tmp_path, filesystem_access="workspace_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        outside = policy.output_dir / "file.txt"  # outside workspace, inside output
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="write_file", write_path=outside)
        assert exc_info.value.allowed_boundary == "workspace_only"


# ---------------------------------------------------------------------------
# validate_tool_request — network checks
# ---------------------------------------------------------------------------

class TestValidateToolRequestNetwork:
    def test_unrestricted_allows_web(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        executor.validate_tool_request(action="fetch_url", destination_type="web")

    def test_unrestricted_allows_other(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        executor.validate_tool_request(action="tcp_connect", destination_type="other")

    def test_none_denies_web(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="none")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="fetch_url", destination_type="web")
        err = exc_info.value
        assert err.reason_code == "network_access_disallowed"
        assert err.policy_field == "sandbox.network_access"

    def test_none_denies_other(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="none")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError):
            executor.validate_tool_request(action="tcp_connect", destination_type="other")

    def test_web_only_allows_web(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="web_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        executor.validate_tool_request(action="fetch_url", destination_type="web")

    def test_web_only_denies_other(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="web_only")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="tcp_connect", destination_type="other")
        err = exc_info.value
        assert err.reason_code == "network_access_disallowed"

    def test_no_destination_type_does_not_raise(self, tmp_path):
        """Requests that don't declare a network destination are not blocked."""
        policy = _make_policy(tmp_path, network_access="none")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        executor.validate_tool_request(action="local_compute")

    def test_error_carries_requested_action(self, tmp_path):
        policy = _make_policy(tmp_path, network_access="none")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="fetch_url", destination_type="web")
        assert exc_info.value.requested_action == "fetch_url"


# ---------------------------------------------------------------------------
# validate_tool_request — combined write + network
# ---------------------------------------------------------------------------

class TestValidateToolRequestCombined:
    def test_both_checks_can_pass(self, tmp_path):
        policy = _make_policy(
            tmp_path,
            filesystem_access="output_only",
            network_access="web_only",
        )
        executor = SandboxExecutor(policy, policy.workspace_dir)
        inside = policy.output_dir / "out.txt"
        executor.validate_tool_request(
            action="search_and_write",
            write_path=inside,
            destination_type="web",
        )

    def test_write_denied_even_if_network_ok(self, tmp_path):
        policy = _make_policy(
            tmp_path,
            filesystem_access="output_only",
            network_access="unrestricted",
        )
        executor = SandboxExecutor(policy, policy.workspace_dir)
        outside = tmp_path / "outside.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(
                action="write_result",
                write_path=outside,
                destination_type="web",
            )
        assert exc_info.value.reason_code == "write_outside_allowed_roots"

    def test_network_denied_even_if_write_ok(self, tmp_path):
        policy = _make_policy(
            tmp_path,
            filesystem_access="output_only",
            network_access="none",
        )
        executor = SandboxExecutor(policy, policy.workspace_dir)
        inside = policy.output_dir / "out.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(
                action="fetch_and_write",
                write_path=inside,
                destination_type="web",
            )
        assert exc_info.value.reason_code == "network_access_disallowed"


# ---------------------------------------------------------------------------
# Orchestrator integration — executor wired into AutoResearcher
# ---------------------------------------------------------------------------

def _make_researcher(tmp_path: Path, security_overrides: dict | None = None, **kwargs):
    """Return a minimal AutoResearcher with optional security config overrides.

    *kwargs* are passed directly as ``SandboxConfig`` fields (e.g.
    ``network_access="none"``).
    """
    from unittest.mock import MagicMock
    from src.config import (
        BackendsConfig, ExecutionConfig, ResearchConfig, ScoringConfig,
        SecurityConfig, SandboxConfig,
    )
    from src.orchestrator import AutoResearcher

    sandbox_kwargs = dict(kwargs)
    security_kwargs = {}
    if security_overrides:
        for k, v in security_overrides.items():
            if k.startswith("sandbox_"):
                sandbox_kwargs[k[len("sandbox_"):]] = v
            else:
                security_kwargs[k] = v

    sandbox = SandboxConfig(**sandbox_kwargs) if sandbox_kwargs else SandboxConfig()
    security = SecurityConfig(sandbox=sandbox, **security_kwargs)

    config = ResearchConfig(
        topic="Test topic",
        goal="Test goal",
        dimensions=("dim1",),
        execution=ExecutionConfig(
            backend="claude-cli",
            backends=BackendsConfig(primary="claude-cli"),
        ),
        scoring=ScoringConfig(),
        security=security,
    )
    backend = MagicMock()
    backend.name = "claude-cli"
    backend.supports_tools = False
    return AutoResearcher(config, backend, tmp_path)


class TestOrchestratorSandboxIntegration:
    """Prove SandboxExecutor is wired into AutoResearcher."""

    def test_sandbox_attribute_exists_before_setup(self, tmp_path):
        """_sandbox must exist on the researcher (may be None before setup)."""
        researcher = _make_researcher(tmp_path)
        # attribute must exist — either None or a SandboxExecutor
        assert hasattr(researcher, "_sandbox")

    def test_guard_path_write_allows_output_dir_path(self, tmp_path):
        researcher = _make_researcher(tmp_path)
        inside = researcher.output_dir / "result.txt"
        researcher.guard_path_write(inside)  # must not raise

    def test_guard_path_write_denies_outside_path(self, tmp_path):
        researcher = _make_researcher(tmp_path)
        outside = tmp_path.parent / "escape.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_path_write(outside)
        err = exc_info.value
        assert err.reason_code == "write_outside_allowed_roots"
        assert err.policy_field == "sandbox.filesystem_access"
        assert err.allowed_boundary == "output_only"

    def test_guard_path_write_workspace_only_denies_output_root(self, tmp_path):
        researcher = _make_researcher(
            tmp_path, security_overrides={"sandbox_filesystem_access": "workspace_only"}
        )
        output_root_file = researcher.output_dir / "file.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_path_write(output_root_file)
        assert exc_info.value.reason_code == "write_outside_allowed_roots"
        assert exc_info.value.allowed_boundary == "workspace_only"

    def test_guard_path_write_workspace_only_allows_workspace_path(self, tmp_path):
        researcher = _make_researcher(
            tmp_path, security_overrides={"sandbox_filesystem_access": "workspace_only"}
        )
        workspace_file = researcher.paths.workspace_dir / "file.txt"
        researcher.guard_path_write(workspace_file)  # must not raise

    def test_guard_path_write_broad_write_allows_outside(self, tmp_path):
        researcher = _make_researcher(
            tmp_path,
            security_overrides={"allow_filesystem_write_outside_output": True},
        )
        anywhere = tmp_path.parent / "anywhere.txt"
        researcher.guard_path_write(anywhere)  # must not raise

    def test_guard_path_write_uses_executor_not_fresh_policy_resolution(self, tmp_path):
        """After setup, guard_path_write must delegate to the cached executor."""
        researcher = _make_researcher(tmp_path)
        # Ensure _sandbox is populated after setup (via _setup_run would create dirs;
        # here we check the guard still produces the executor-consistent denial payload)
        outside = tmp_path.parent / "escape.txt"
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_path_write(outside)
        # payload must match executor contract: policy token, not path basename
        assert exc_info.value.allowed_boundary == "output_only"
        assert exc_info.value.policy_field == "sandbox.filesystem_access"


# ---------------------------------------------------------------------------
# Orchestrator network policy integration — guard_network_action
# ---------------------------------------------------------------------------

def _make_sandboxed_researcher(tmp_path: Path, *, network_access: str = "none") -> object:
    """Return an AutoResearcher with sandbox active and the given network_access."""
    from src.config import (
        BackendsConfig, ExecutionConfig, ResearchConfig, ScoringConfig,
        SecurityConfig, SandboxConfig,
    )
    from src.orchestrator import AutoResearcher
    from unittest.mock import MagicMock

    sandbox = SandboxConfig(mode="tool_calls", network_access=network_access)
    security = SecurityConfig(tool_execution_mode="sandboxed", sandbox=sandbox)
    config = ResearchConfig(
        topic="t",
        goal="g",
        dimensions=("d1",),
        execution=ExecutionConfig(
            backend="claude-cli",
            backends=BackendsConfig(primary="claude-cli"),
        ),
        scoring=ScoringConfig(),
        security=security,
    )
    backend = MagicMock()
    backend.name = "claude-cli"
    backend.supports_tools = False
    return AutoResearcher(config, backend, tmp_path)


class TestOrchestratorNetworkPolicyIntegration:
    """Prove guard_network_action is wired and enforces network policy."""

    def test_guard_network_action_method_exists(self, tmp_path):
        researcher = _make_researcher(tmp_path)
        assert hasattr(researcher, "guard_network_action")
        assert callable(researcher.guard_network_action)

    # -- unrestricted allows everything ------------------------------------

    def test_unrestricted_allows_web_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="unrestricted")
        researcher.guard_network_action("fetch_url", "web")  # must not raise

    def test_unrestricted_allows_other_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="unrestricted")
        researcher.guard_network_action("tcp_connect", "other")  # must not raise

    # -- none denies everything -------------------------------------------

    def test_none_denies_web_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="none")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("fetch_url", "web")
        err = exc_info.value
        assert err.reason_code == "network_access_disallowed"
        assert err.policy_field == "sandbox.network_access"

    def test_none_denies_other_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="none")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("tcp_connect", "other")
        assert exc_info.value.reason_code == "network_access_disallowed"

    # -- web_only: web passes, other denied --------------------------------

    def test_web_only_allows_web_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="web_only")
        researcher.guard_network_action("web_search", "web")  # must not raise

    def test_web_only_denies_other_destination(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="web_only")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("tcp_connect", "other")
        assert exc_info.value.reason_code == "network_access_disallowed"

    # -- denial payload ----------------------------------------------------

    def test_denial_carries_allowed_boundary_none(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="none")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("fetch_url", "web")
        assert exc_info.value.allowed_boundary == "none"

    def test_denial_carries_allowed_boundary_web_only(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="web_only")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("tcp_connect", "other")
        assert exc_info.value.allowed_boundary == "web_only"

    def test_denial_carries_requested_action(self, tmp_path):
        researcher = _make_sandboxed_researcher(tmp_path, network_access="none")
        with pytest.raises(PolicyDeniedError) as exc_info:
            researcher.guard_network_action("my_action", "web")
        assert exc_info.value.requested_action == "my_action"

    # -- direct mode: no enforcement ---------------------------------------

    def test_direct_mode_does_not_enforce_even_with_network_none(self, tmp_path):
        """Sandbox_active=False → guard_network_action is a no-op regardless of config."""
        researcher = _make_researcher(tmp_path, network_access="none")
        # direct mode: no PolicyDeniedError
        researcher.guard_network_action("fetch_url", "web")  # must not raise

    # -- audit event -------------------------------------------------------

    def test_network_denial_emits_policy_denied_audit_event(self, tmp_path):
        import json
        researcher = _make_sandboxed_researcher(tmp_path, network_access="none")
        with pytest.raises(PolicyDeniedError):
            researcher.guard_network_action("fetch_url", "web")
        trail = researcher.paths.audit_trail
        events = [json.loads(l) for l in trail.read_text(encoding="utf-8").splitlines()]
        denial_events = [e for e in events if e.get("event") == "policy_denied"]
        assert len(denial_events) == 1
        assert denial_events[0]["reason_code"] == "network_access_disallowed"


# ---------------------------------------------------------------------------
# SandboxExecutor.build_environment
# ---------------------------------------------------------------------------

class TestBuildEnvironment:
    """Unit tests for SandboxExecutor.build_environment."""

    def test_method_exists_on_executor(self, tmp_path):
        executor = _make_executor(tmp_path)
        assert hasattr(executor, "build_environment")
        assert callable(executor.build_environment)

    # -- allowlisted keys are preserved -----------------------------------

    def test_path_is_preserved(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"PATH": "/usr/bin:/bin"})
        assert env["PATH"] == "/usr/bin:/bin"

    def test_home_is_preserved(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"HOME": "/home/user", "PATH": "/usr/bin"})
        assert env["HOME"] == "/home/user"

    def test_lang_is_preserved(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"LANG": "en_US.UTF-8"})
        assert env["LANG"] == "en_US.UTF-8"

    def test_proxy_vars_are_preserved(self, tmp_path):
        executor = _make_executor(tmp_path)
        base = {
            "HTTP_PROXY": "http://proxy:3128",
            "HTTPS_PROXY": "http://proxy:3128",
            "NO_PROXY": "localhost",
        }
        env = executor.build_environment(base)
        assert env["HTTP_PROXY"] == "http://proxy:3128"
        assert env["HTTPS_PROXY"] == "http://proxy:3128"
        assert env["NO_PROXY"] == "localhost"

    def test_api_keys_are_preserved(self, tmp_path):
        """API keys must survive env shaping so backend subprocesses can call their APIs."""
        executor = _make_executor(tmp_path)
        base = {
            "ANTHROPIC_API_KEY": "sk-ant-secret",
            "OPENAI_API_KEY": "sk-openai-secret",
        }
        env = executor.build_environment(base)
        assert env["ANTHROPIC_API_KEY"] == "sk-ant-secret"
        assert env["OPENAI_API_KEY"] == "sk-openai-secret"

    # -- non-allowlisted keys are stripped --------------------------------

    def test_ssh_auth_sock_is_stripped(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock"})
        assert "SSH_AUTH_SOCK" not in env

    def test_gpg_agent_info_is_stripped(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"GPG_AGENT_INFO": "/run/user/1000/gnupg"})
        assert "GPG_AGENT_INFO" not in env

    def test_histfile_is_stripped(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"HISTFILE": "/home/user/.bash_history"})
        assert "HISTFILE" not in env

    def test_ci_env_var_is_stripped(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"CI": "true", "GITHUB_ACTIONS": "true"})
        assert "CI" not in env
        assert "GITHUB_ACTIONS" not in env

    def test_arbitrary_unknown_var_is_stripped(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"MY_CUSTOM_SECRET": "hunter2"})
        assert "MY_CUSTOM_SECRET" not in env

    # -- edge cases -------------------------------------------------------

    def test_empty_base_env_returns_empty_dict(self, tmp_path):
        executor = _make_executor(tmp_path)
        assert executor.build_environment({}) == {}

    def test_returns_new_dict_not_same_object(self, tmp_path):
        executor = _make_executor(tmp_path)
        base = {"PATH": "/usr/bin"}
        result = executor.build_environment(base)
        assert result is not base

    def test_source_env_is_not_mutated(self, tmp_path):
        executor = _make_executor(tmp_path)
        base = {"PATH": "/usr/bin", "SSH_AUTH_SOCK": "/tmp/sock"}
        original = dict(base)
        executor.build_environment(base)
        assert base == original

    def test_none_base_env_uses_os_environ(self, tmp_path, monkeypatch):
        """When base_env=None, os.environ is the source (not an empty dict)."""
        monkeypatch.setenv("PATH", "/injected/path")
        executor = _make_executor(tmp_path)
        env = executor.build_environment(None)
        assert env.get("PATH") == "/injected/path"

    # -- case-insensitive matching (Windows compatibility) ----------------

    def test_lowercase_key_in_allowlist_is_still_preserved(self, tmp_path):
        """Allowlist matching is case-insensitive so Windows vars survive."""
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"path": "/usr/bin"})
        assert env.get("path") == "/usr/bin"

    def test_mixed_case_key_in_allowlist_is_preserved(self, tmp_path):
        executor = _make_executor(tmp_path)
        env = executor.build_environment({"Path": "/usr/bin"})
        assert env.get("Path") == "/usr/bin"

    # -- deterministic ----------------------------------------------------

    def test_same_input_produces_same_output(self, tmp_path):
        executor = _make_executor(tmp_path)
        base = {"PATH": "/usr/bin", "HOME": "/home/user", "SSH_AUTH_SOCK": "/tmp/sock"}
        assert executor.build_environment(base) == executor.build_environment(base)


# ---------------------------------------------------------------------------
# M5 wiring: _resolve_env prefers process_env over build_process_env
# ---------------------------------------------------------------------------

class TestResolveEnv:
    """BaseBackend._resolve_env uses process_env when set, sanitize otherwise."""

    def _make_backend(self):
        from src.backends import get_backend
        return get_backend("claude-cli")

    def test_resolve_env_returns_process_env_when_set(self):
        """If opts.process_env is set, _resolve_env must return it directly."""
        from src.backends.types import CallOptions
        backend = self._make_backend()
        explicit_env = {"PATH": "/usr/bin", "HOME": "/home/user"}
        opts = CallOptions(process_env=explicit_env)
        result = backend._resolve_env(opts)
        assert result is explicit_env

    def test_resolve_env_falls_back_to_sanitize_when_process_env_is_none(self):
        """If opts.process_env is None and sanitize=True, _resolve_env returns sanitized env."""
        from src.backends.types import CallOptions
        from src.backends.base import Backend as BaseBackend
        backend = self._make_backend()
        opts = CallOptions(sanitize_environment=True)
        result = backend._resolve_env(opts)
        expected = BaseBackend.build_process_env(sanitize=True)
        assert result == expected

    def test_resolve_env_returns_none_when_both_unset(self):
        """If opts.process_env is None and sanitize=False, _resolve_env returns None."""
        from src.backends.types import CallOptions
        backend = self._make_backend()
        opts = CallOptions()
        result = backend._resolve_env(opts)
        assert result is None

    def test_resolve_env_process_env_wins_over_sanitize(self):
        """Process_env takes precedence even when sanitize_environment=True."""
        from src.backends.types import CallOptions
        backend = self._make_backend()
        explicit_env = {"PATH": "/custom"}
        opts = CallOptions(process_env=explicit_env, sanitize_environment=True)
        result = backend._resolve_env(opts)
        assert result is explicit_env


# ---------------------------------------------------------------------------
# destination_type validation in _check_network
# ---------------------------------------------------------------------------

class TestValidateToolRequestDestinationTypeValidation:
    """Invalid destination_type values must fail with a clear denial reason."""

    def test_invalid_destination_type_raises_policy_denied(self, tmp_path):
        from src.policy.policy_denial import PolicyDeniedError
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="dispatch", destination_type="invalid_stuff")
        assert exc_info.value.reason_code == "invalid_destination_type"

    def test_invalid_destination_type_denied_even_in_unrestricted_mode(self, tmp_path):
        """Invalid destination_type must fail even when network policy is unrestricted."""
        from src.policy.policy_denial import PolicyDeniedError
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="dispatch", destination_type="weeb")
        assert exc_info.value.reason_code == "invalid_destination_type"
        assert exc_info.value.policy_field == "sandbox.network_access"

    def test_invalid_destination_type_carries_requested_action(self, tmp_path):
        from src.policy.policy_denial import PolicyDeniedError
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        with pytest.raises(PolicyDeniedError) as exc_info:
            executor.validate_tool_request(action="tool_dispatch:BrokenTool", destination_type="http")
        assert exc_info.value.requested_action == "tool_dispatch:BrokenTool"

    def test_valid_web_destination_type_passes(self, tmp_path):
        """'web' is a valid destination_type and must not raise invalid_destination_type."""
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        # Should not raise — valid destination type in unrestricted mode
        executor.validate_tool_request(action="dispatch", destination_type="web")

    def test_valid_other_destination_type_passes(self, tmp_path):
        """'other' is a valid destination_type and must not raise invalid_destination_type."""
        policy = _make_policy(tmp_path, network_access="unrestricted")
        executor = SandboxExecutor(policy, policy.workspace_dir)
        executor.validate_tool_request(action="dispatch", destination_type="other")
