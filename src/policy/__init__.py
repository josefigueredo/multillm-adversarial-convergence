"""Policy domain package.

Re-exports the HITL / trust / policy / security / sandbox API under a single
package boundary.  Canonical paths are ``src.policy.<module>``; flat-module
imports were removed in MM15 Step 7.

Contexts exposed:
- HITL: human-in-the-loop models and I/O helpers
- Policy denial: error type for enforcement refusals
- Trust: citation and claim trust classification
- Security runtime: effective runtime security policy resolution
- Tool capabilities: tool classification registry and helpers
- Tool runtime: function-tool execution loop
- Sandbox executor: executor abstraction for sandboxed runs
"""

from __future__ import annotations

# ── HITL ──────────────────────────────────────────────────────────────────────
from .hitl import (
    DeferReason,
    HumanDecision,
    HumanInputRequest,
    append_human_decisions,
    collect_interactive,
    load_human_decisions,
    write_pending_questions,
)

# ── Policy denial ─────────────────────────────────────────────────────────────
from .policy_denial import PolicyDeniedError

# ── Trust ─────────────────────────────────────────────────────────────────────
from .trust import classify_citation_trust, classify_claim_trust, trust_summary

# ── Security runtime ──────────────────────────────────────────────────────────
from .security_runtime import RuntimeSecurityPolicy, resolve_runtime_security_policy

# ── Tool capabilities ─────────────────────────────────────────────────────────
from .tool_capabilities import (
    ToolCapabilities,
    check_capability_consistency,
    classify_allowed_tools,
    classify_tool,
    coverage_stats,
)

# ── Tool runtime ──────────────────────────────────────────────────────────────
from .tool_runtime import run_function_tool_loop

# ── Sandbox executor ──────────────────────────────────────────────────────────
from .sandbox_executor import SandboxExecutor

__all__ = [
    # hitl
    "DeferReason",
    "HumanInputRequest",
    "HumanDecision",
    "collect_interactive",
    "write_pending_questions",
    "load_human_decisions",
    "append_human_decisions",
    # policy denial
    "PolicyDeniedError",
    # trust
    "classify_citation_trust",
    "classify_claim_trust",
    "trust_summary",
    # security runtime
    "RuntimeSecurityPolicy",
    "resolve_runtime_security_policy",
    # tool capabilities
    "ToolCapabilities",
    "classify_tool",
    "classify_allowed_tools",
    "coverage_stats",
    "check_capability_consistency",
    # tool runtime
    "run_function_tool_loop",
    # sandbox executor
    "SandboxExecutor",
]
