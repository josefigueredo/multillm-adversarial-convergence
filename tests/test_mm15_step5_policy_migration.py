"""MM15 Step 5 — policy Phase A: canonical module paths + shim backward compat."""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical new-path imports
# ---------------------------------------------------------------------------

class TestPolicyCanonicalPaths:
    def test_hitl_module_importable_at_canonical_path(self):
        from src.policy import hitl  # noqa: F401
        assert hitl is not None

    def test_policy_denial_module_importable_at_canonical_path(self):
        from src.policy import policy_denial  # noqa: F401
        assert policy_denial is not None

    def test_trust_module_importable_at_canonical_path(self):
        from src.policy import trust  # noqa: F401
        assert trust is not None

    def test_security_runtime_module_importable_at_canonical_path(self):
        from src.policy import security_runtime  # noqa: F401
        assert security_runtime is not None

    def test_tool_capabilities_module_importable_at_canonical_path(self):
        from src.policy import tool_capabilities  # noqa: F401
        assert tool_capabilities is not None

    def test_tool_runtime_module_importable_at_canonical_path(self):
        from src.policy import tool_runtime  # noqa: F401
        assert tool_runtime is not None

    def test_sandbox_executor_module_importable_at_canonical_path(self):
        from src.policy import sandbox_executor  # noqa: F401
        assert sandbox_executor is not None

    def test_human_input_request_from_canonical_hitl(self):
        from src.policy.hitl import HumanInputRequest
        assert HumanInputRequest is not None

    def test_policy_denied_error_from_canonical(self):
        from src.policy.policy_denial import PolicyDeniedError
        assert PolicyDeniedError is not None

    def test_classify_citation_trust_from_canonical(self):
        from src.policy.trust import classify_citation_trust
        assert callable(classify_citation_trust)

    def test_runtime_security_policy_from_canonical(self):
        from src.policy.security_runtime import RuntimeSecurityPolicy
        assert RuntimeSecurityPolicy is not None

    def test_resolve_runtime_security_policy_from_canonical(self):
        from src.policy.security_runtime import resolve_runtime_security_policy
        assert callable(resolve_runtime_security_policy)

    def test_tool_capabilities_class_from_canonical(self):
        from src.policy.tool_capabilities import ToolCapabilities
        assert ToolCapabilities is not None

    def test_classify_tool_from_canonical(self):
        from src.policy.tool_capabilities import classify_tool
        assert callable(classify_tool)

    def test_run_function_tool_loop_from_canonical(self):
        from src.policy.tool_runtime import run_function_tool_loop
        assert callable(run_function_tool_loop)

    def test_sandbox_executor_class_from_canonical(self):
        from src.policy.sandbox_executor import SandboxExecutor
        assert SandboxExecutor is not None


# ---------------------------------------------------------------------------
# Old flat-path imports must still work via compatibility shims
# ---------------------------------------------------------------------------

class TestPolicyShimBackwardCompat:
    def test_hitl_human_input_request_from_src_hitl(self):
        from src.hitl import HumanInputRequest
        assert HumanInputRequest is not None

    def test_hitl_defer_reason_from_src_hitl(self):
        from src.hitl import DeferReason
        assert DeferReason is not None

    def test_policy_denied_error_from_src_policy_denial(self):
        from src.policy_denial import PolicyDeniedError
        assert PolicyDeniedError is not None

    def test_classify_citation_trust_from_src_trust(self):
        from src.trust import classify_citation_trust
        assert callable(classify_citation_trust)

    def test_runtime_security_policy_from_src_security_runtime(self):
        from src.security_runtime import RuntimeSecurityPolicy
        assert RuntimeSecurityPolicy is not None

    def test_resolve_runtime_security_policy_from_src_security_runtime(self):
        from src.security_runtime import resolve_runtime_security_policy
        assert callable(resolve_runtime_security_policy)

    def test_tool_capabilities_from_src_tool_capabilities(self):
        from src.tool_capabilities import ToolCapabilities
        assert ToolCapabilities is not None

    def test_classify_tool_from_src_tool_capabilities(self):
        from src.tool_capabilities import classify_tool
        assert callable(classify_tool)

    def test_run_function_tool_loop_from_src_tool_runtime(self):
        from src.tool_runtime import run_function_tool_loop
        assert callable(run_function_tool_loop)

    def test_sandbox_executor_from_src_sandbox_executor(self):
        from src.sandbox_executor import SandboxExecutor
        assert SandboxExecutor is not None


# ---------------------------------------------------------------------------
# Regression: existing src.policy package __init__ API still intact
# ---------------------------------------------------------------------------

class TestPolicyPackageApiUnchanged:
    def test_human_input_request_via_policy_init(self):
        from src.policy import HumanInputRequest
        assert HumanInputRequest is not None

    def test_policy_denied_error_via_policy_init(self):
        from src.policy import PolicyDeniedError
        assert PolicyDeniedError is not None

    def test_classify_citation_trust_via_policy_init(self):
        from src.policy import classify_citation_trust
        assert callable(classify_citation_trust)

    def test_runtime_security_policy_via_policy_init(self):
        from src.policy import RuntimeSecurityPolicy
        assert RuntimeSecurityPolicy is not None

    def test_tool_capabilities_via_policy_init(self):
        from src.policy import ToolCapabilities
        assert ToolCapabilities is not None

    def test_run_function_tool_loop_via_policy_init(self):
        from src.policy import run_function_tool_loop
        assert callable(run_function_tool_loop)

    def test_sandbox_executor_via_policy_init(self):
        from src.policy import SandboxExecutor
        assert SandboxExecutor is not None


# ---------------------------------------------------------------------------
# Module identity: shim and canonical must resolve to the same object
# (so `isinstance` and class-identity assertions in legacy callers stay valid)
# ---------------------------------------------------------------------------

class TestPolicyModuleIdentity:
    def test_policy_denied_error_identity(self):
        from src.policy.policy_denial import PolicyDeniedError as Canonical
        from src.policy_denial import PolicyDeniedError as Shimmed
        assert Canonical is Shimmed

    def test_human_input_request_identity(self):
        from src.policy.hitl import HumanInputRequest as Canonical
        from src.hitl import HumanInputRequest as Shimmed
        assert Canonical is Shimmed

    def test_runtime_security_policy_identity(self):
        from src.policy.security_runtime import RuntimeSecurityPolicy as Canonical
        from src.security_runtime import RuntimeSecurityPolicy as Shimmed
        assert Canonical is Shimmed

    def test_tool_capabilities_identity(self):
        from src.policy.tool_capabilities import ToolCapabilities as Canonical
        from src.tool_capabilities import ToolCapabilities as Shimmed
        assert Canonical is Shimmed

    def test_sandbox_executor_identity(self):
        from src.policy.sandbox_executor import SandboxExecutor as Canonical
        from src.sandbox_executor import SandboxExecutor as Shimmed
        assert Canonical is Shimmed
