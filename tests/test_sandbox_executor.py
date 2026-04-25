"""Tests for src.sandbox_executor — SandboxExecutor abstraction (M4 Step 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.sandbox_executor import SandboxExecutor
from src.security_runtime import RuntimeSecurityPolicy
from src.policy_denial import PolicyDeniedError


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
