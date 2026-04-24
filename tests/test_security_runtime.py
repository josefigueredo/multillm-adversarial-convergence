"""Tests for src.security_runtime — RuntimeSecurityPolicy resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import SandboxConfig, SecurityConfig
from src.run_paths import RunPaths
from src.security_runtime import RuntimeSecurityPolicy, resolve_runtime_security_policy


def _paths(tmp_path: Path) -> RunPaths:
    return RunPaths.for_output_dir(tmp_path / "output" / "run-test")


def _policy(
    tmp_path: Path,
    *,
    content_trust: str = "strict",
    tool_execution_mode: str = "direct",
    allow_host_bash: bool = True,
    allow_filesystem_write_outside_output: bool = False,
    sandbox_mode: str = "off",
    filesystem_access: str = "output_only",
    network_access: str = "unrestricted",
) -> RuntimeSecurityPolicy:
    sec = SecurityConfig(
        content_trust=content_trust,
        tool_execution_mode=tool_execution_mode,
        allow_host_bash=allow_host_bash,
        allow_filesystem_write_outside_output=allow_filesystem_write_outside_output,
        sandbox=SandboxConfig(
            mode=sandbox_mode,
            filesystem_access=filesystem_access,
            network_access=network_access,
        ),
    )
    return resolve_runtime_security_policy(sec, _paths(tmp_path))


# ---------------------------------------------------------------------------
# resolve_runtime_security_policy returns RuntimeSecurityPolicy
# ---------------------------------------------------------------------------

class TestResolveReturnType:
    def test_returns_runtime_security_policy(self, tmp_path: Path):
        policy = _policy(tmp_path)
        assert isinstance(policy, RuntimeSecurityPolicy)

    def test_is_frozen(self, tmp_path: Path):
        policy = _policy(tmp_path)
        with pytest.raises((AttributeError, TypeError)):
            policy.tool_execution_mode = "something"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# is_tool_execution_allowed
# ---------------------------------------------------------------------------

class TestIsToolExecutionAllowed:
    def test_direct_mode_allows_tool_execution(self, tmp_path: Path):
        policy = _policy(tmp_path, tool_execution_mode="direct")
        assert policy.is_tool_execution_allowed() is True

    def test_sandboxed_mode_allows_tool_execution(self, tmp_path: Path):
        # sandboxed = audit/warn in Milestone 2; not a hard block
        policy = _policy(tmp_path, tool_execution_mode="sandboxed")
        assert policy.is_tool_execution_allowed() is True

    def test_sandboxed_with_tool_calls_mode_is_sandbox_active(self, tmp_path: Path):
        policy = _policy(tmp_path, tool_execution_mode="sandboxed", sandbox_mode="tool_calls")
        assert policy.sandbox_active is True

    def test_sandboxed_with_sandbox_mode_off_is_not_active(self, tmp_path: Path):
        # tool_execution_mode=sandboxed alone is insufficient; sandbox.mode must also be tool_calls
        policy = _policy(tmp_path, tool_execution_mode="sandboxed", sandbox_mode="off")
        assert policy.sandbox_active is False

    def test_direct_mode_never_sandbox_active(self, tmp_path: Path):
        policy = _policy(tmp_path, tool_execution_mode="direct", sandbox_mode="tool_calls")
        assert policy.sandbox_active is False

    def test_direct_mode_not_sandboxed(self, tmp_path: Path):
        policy = _policy(tmp_path, tool_execution_mode="direct")
        assert policy.sandbox_active is False


# ---------------------------------------------------------------------------
# is_host_bash_allowed
# ---------------------------------------------------------------------------

class TestIsHostBashAllowed:
    def test_default_allows_host_bash(self, tmp_path: Path):
        policy = _policy(tmp_path)
        assert policy.is_host_bash_allowed() is True

    def test_disabled_denies_host_bash(self, tmp_path: Path):
        policy = _policy(tmp_path, allow_host_bash=False)
        assert policy.is_host_bash_allowed() is False


# ---------------------------------------------------------------------------
# allowed_write_roots
# ---------------------------------------------------------------------------

class TestAllowedWriteRoots:
    def test_output_only_returns_output_dir(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="output_only")
        roots = policy.allowed_write_roots()
        paths = _paths(tmp_path)
        assert paths.output_dir in roots
        assert len(roots) == 1

    def test_workspace_only_returns_workspace_dir(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="workspace_only")
        roots = policy.allowed_write_roots()
        paths = _paths(tmp_path)
        assert paths.output_dir / ".workspace" in roots

    def test_workspace_only_does_not_include_arbitrary_paths(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="workspace_only")
        roots = policy.allowed_write_roots()
        assert tmp_path not in roots

    def test_write_within_output_dir_is_allowed(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="output_only")
        paths = _paths(tmp_path)
        candidate = paths.output_dir / "results.tsv"
        assert policy.is_write_allowed(candidate) is True

    def test_write_outside_output_dir_is_denied(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="output_only")
        candidate = tmp_path / "evil.sh"
        assert policy.is_write_allowed(candidate) is False

    def test_write_within_workspace_dir_is_allowed(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="workspace_only")
        paths = _paths(tmp_path)
        candidate = paths.output_dir / ".workspace" / "scratch.py"
        assert policy.is_write_allowed(candidate) is True

    def test_write_outside_workspace_is_denied(self, tmp_path: Path):
        policy = _policy(tmp_path, filesystem_access="workspace_only")
        paths = _paths(tmp_path)
        candidate = paths.output_dir / "results.tsv"  # output_dir root, not .workspace
        # workspace_only restricts to workspace subdir
        assert policy.is_write_allowed(candidate) is False

    def test_writes_outside_output_allowed_returns_false_by_default(self, tmp_path: Path):
        policy = _policy(tmp_path)
        assert policy.writes_outside_output_allowed() is False

    def test_writes_outside_output_allowed_when_flag_set(self, tmp_path: Path):
        policy = _policy(tmp_path, allow_filesystem_write_outside_output=True)
        assert policy.writes_outside_output_allowed() is True

    def test_allow_filesystem_write_outside_output_permits_any_path(self, tmp_path: Path):
        policy = _policy(tmp_path, allow_filesystem_write_outside_output=True)
        # any path is now allowed because the operator explicitly declared broad write access
        assert policy.is_write_allowed(tmp_path / "evil.sh") is True
        assert policy.is_write_allowed(Path("/tmp/anything")) is True

    def test_default_policy_still_denies_outside_paths(self, tmp_path: Path):
        policy = _policy(tmp_path, allow_filesystem_write_outside_output=False)
        assert policy.is_write_allowed(tmp_path / "outside.txt") is False


# ---------------------------------------------------------------------------
# network_mode
# ---------------------------------------------------------------------------

class TestNetworkMode:
    def test_unrestricted_mode(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="unrestricted")
        assert policy.network_mode() == "unrestricted"

    def test_web_only_mode(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="web_only")
        assert policy.network_mode() == "web_only"

    def test_none_mode(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="none")
        assert policy.network_mode() == "none"

    def test_web_only_allows_web_destinations(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="web_only")
        assert policy.is_network_allowed(destination_type="web") is True

    def test_web_only_denies_other_destinations(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="web_only")
        assert policy.is_network_allowed(destination_type="other") is False

    def test_none_denies_all_destinations(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="none")
        assert policy.is_network_allowed(destination_type="web") is False
        assert policy.is_network_allowed(destination_type="other") is False

    def test_unrestricted_allows_all_destinations(self, tmp_path: Path):
        policy = _policy(tmp_path, network_access="unrestricted")
        assert policy.is_network_allowed(destination_type="web") is True
        assert policy.is_network_allowed(destination_type="other") is True


# ---------------------------------------------------------------------------
# policy carries resolved paths
# ---------------------------------------------------------------------------

class TestPolicyPaths:
    def test_output_dir_preserved(self, tmp_path: Path):
        policy = _policy(tmp_path)
        paths = _paths(tmp_path)
        assert policy.output_dir == paths.output_dir

    def test_workspace_dir_is_under_output_dir(self, tmp_path: Path):
        policy = _policy(tmp_path)
        assert policy.workspace_dir.parent == policy.output_dir
        assert policy.workspace_dir.name == ".workspace"
