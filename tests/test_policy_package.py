"""Policy domain package seam tests.

TDD tests that verify:
- src.policy exposes the full HITL/trust/policy/security API
- Package __all__ is canonical and complete
"""
from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
# src.policy — HITL / policy / trust / security / sandbox surface
# ══════════════════════════════════════════════════════════════════════════════


class TestPolicyPackageImportable:
    def test_package_importable(self):
        import src.policy  # noqa: F401


# ── HITL ─────────────────────────────────────────────────────────────────────

class TestHITLTypes:
    def test_defer_reason(self):
        from src.policy import DeferReason
        assert DeferReason is not None

    def test_human_input_request(self):
        from src.policy import HumanInputRequest
        assert HumanInputRequest is not None

    def test_human_decision(self):
        from src.policy import HumanDecision
        assert HumanDecision is not None

    def test_collect_interactive(self):
        from src.policy import collect_interactive
        assert callable(collect_interactive)

    def test_write_pending_questions(self):
        from src.policy import write_pending_questions
        assert callable(write_pending_questions)

    def test_load_human_decisions(self):
        from src.policy import load_human_decisions
        assert callable(load_human_decisions)

    def test_append_human_decisions(self):
        from src.policy import append_human_decisions
        assert callable(append_human_decisions)


# ── Policy denial ─────────────────────────────────────────────────────────────

class TestPolicyDenialTypes:
    def test_policy_denied_error(self):
        from src.policy import PolicyDeniedError
        assert issubclass(PolicyDeniedError, Exception)

    def test_policy_denied_error_is_exception(self):
        from src.policy import PolicyDeniedError
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="bash",
        )
        assert isinstance(err, Exception)


# ── Trust ─────────────────────────────────────────────────────────────────────

class TestTrustFunctions:
    def test_classify_citation_trust(self):
        from src.policy import classify_citation_trust
        assert callable(classify_citation_trust)

    def test_classify_claim_trust(self):
        from src.policy import classify_claim_trust
        assert callable(classify_claim_trust)

    def test_trust_summary(self):
        from src.policy import trust_summary
        assert callable(trust_summary)


# ── Security runtime ──────────────────────────────────────────────────────────

class TestSecurityRuntimeTypes:
    def test_runtime_security_policy(self):
        from src.policy import RuntimeSecurityPolicy
        assert RuntimeSecurityPolicy is not None

    def test_resolve_runtime_security_policy(self):
        from src.policy import resolve_runtime_security_policy
        assert callable(resolve_runtime_security_policy)


# ── Tool capabilities ─────────────────────────────────────────────────────────

class TestToolCapabilitiesTypes:
    def test_tool_capabilities(self):
        from src.policy import ToolCapabilities
        assert ToolCapabilities is not None

    def test_classify_tool(self):
        from src.policy import classify_tool
        assert callable(classify_tool)

    def test_classify_allowed_tools(self):
        from src.policy import classify_allowed_tools
        assert callable(classify_allowed_tools)

    def test_coverage_stats(self):
        from src.policy import coverage_stats
        assert callable(coverage_stats)

    def test_check_capability_consistency(self):
        from src.policy import check_capability_consistency
        assert callable(check_capability_consistency)


# ── Tool runtime ──────────────────────────────────────────────────────────────

class TestToolRuntimeFunctions:
    def test_run_function_tool_loop(self):
        from src.policy import run_function_tool_loop
        assert callable(run_function_tool_loop)


# ── Sandbox executor ──────────────────────────────────────────────────────────

class TestSandboxExecutorType:
    def test_sandbox_executor(self):
        from src.policy import SandboxExecutor
        assert SandboxExecutor is not None


# ── __all__ integrity ─────────────────────────────────────────────────────────

class TestPolicyAllList:
    def test_all_defined(self):
        import src.policy as pkg
        assert hasattr(pkg, "__all__")

    def test_all_members_importable(self):
        import src.policy as pkg
        for name in pkg.__all__:
            assert hasattr(pkg, name), f"src.policy.__all__ lists {name!r} but it is not present"
