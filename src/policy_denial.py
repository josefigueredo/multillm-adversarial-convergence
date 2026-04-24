"""Policy denial model for security enforcement.

Provides PolicyDeniedError — a structured exception raised whenever a
requested action is blocked by the active runtime security policy.
"""

from __future__ import annotations

from typing import Optional


class PolicyDeniedError(Exception):
    """Raised when a requested action is blocked by the runtime security policy.

    Attributes
    ----------
    reason_code:
        Machine-stable token identifying the denial reason.
        Valid values: ``host_bash_disabled``, ``write_outside_allowed_roots``,
        ``network_access_disallowed``, ``tool_calls_disabled``.
    policy_field:
        The config field that caused the denial (e.g. ``allow_host_bash``).
    requested_action:
        Short label for the action that was blocked (e.g. ``execute_bash``).
    requested_path:
        Filesystem path that was blocked, when applicable.
    allowed_boundary:
        The permitted scope that the request violated (e.g. ``output_only``).
    """

    def __init__(
        self,
        *,
        reason_code: str,
        policy_field: str,
        requested_action: str,
        requested_path: Optional[str] = None,
        allowed_boundary: Optional[str] = None,
    ) -> None:
        self.reason_code = reason_code
        self.policy_field = policy_field
        self.requested_action = requested_action
        self.requested_path = requested_path
        self.allowed_boundary = allowed_boundary
        super().__init__(self._format_message())

    # ------------------------------------------------------------------
    # Human-readable message
    # ------------------------------------------------------------------

    def _format_message(self) -> str:
        parts = [
            f"[policy denied] {self.reason_code}",
            f"policy_field={self.policy_field}",
            f"action={self.requested_action}",
        ]
        if self.requested_path is not None:
            parts.append(f"path={self.requested_path}")
        if self.allowed_boundary is not None:
            parts.append(f"allowed={self.allowed_boundary}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Structured audit payload
    # ------------------------------------------------------------------

    def audit_payload(self) -> dict:
        """Return a JSON-serializable dict suitable for audit_trail.jsonl."""
        payload: dict = {
            "reason_code": self.reason_code,
            "policy_field": self.policy_field,
            "requested_action": self.requested_action,
        }
        if self.requested_path is not None:
            payload["requested_path"] = self.requested_path
        if self.allowed_boundary is not None:
            payload["allowed_boundary"] = self.allowed_boundary
        return payload
