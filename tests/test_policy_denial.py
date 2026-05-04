"""Tests for PolicyDeniedError — reason codes, formatting, and structured payload."""

import pytest

from src.policy.policy_denial import PolicyDeniedError


# ---------------------------------------------------------------------------
# Reason codes — each defined value must be accepted
# ---------------------------------------------------------------------------

class TestReasonCodes:
    def test_host_bash_disabled(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        assert err.reason_code == "host_bash_disabled"

    def test_write_outside_allowed_roots(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/evil",
            allowed_boundary="output_only",
        )
        assert err.reason_code == "write_outside_allowed_roots"

    def test_network_access_disallowed(self):
        err = PolicyDeniedError(
            reason_code="network_access_disallowed",
            policy_field="sandbox.network_access",
            requested_action="http_request",
            allowed_boundary="none",
        )
        assert err.reason_code == "network_access_disallowed"

    def test_tool_calls_disabled(self):
        err = PolicyDeniedError(
            reason_code="tool_calls_disabled",
            policy_field="tool_execution_mode",
            requested_action="tool_call",
        )
        assert err.reason_code == "tool_calls_disabled"


# ---------------------------------------------------------------------------
# Message formatting — human-readable, mentions policy field
# ---------------------------------------------------------------------------

class TestMessageFormatting:
    def test_message_mentions_reason_code(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        msg = str(err)
        assert "host_bash_disabled" in msg

    def test_message_mentions_policy_field(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        msg = str(err)
        assert "allow_host_bash" in msg

    def test_message_mentions_requested_action(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        msg = str(err)
        assert "write" in msg

    def test_message_mentions_requested_path_when_present(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        msg = str(err)
        assert "/tmp/bad" in msg

    def test_message_mentions_allowed_boundary_when_present(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        msg = str(err)
        assert "output_only" in msg

    def test_message_without_optional_fields_does_not_crash(self):
        err = PolicyDeniedError(
            reason_code="tool_calls_disabled",
            policy_field="tool_execution_mode",
            requested_action="tool_call",
        )
        msg = str(err)
        assert "tool_calls_disabled" in msg
        assert "tool_execution_mode" in msg

    def test_message_is_operator_friendly_prefix(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        msg = str(err)
        assert msg.startswith("[policy denied]") or "policy denied" in msg.lower()


# ---------------------------------------------------------------------------
# Structured audit payload
# ---------------------------------------------------------------------------

class TestAuditPayload:
    def test_payload_contains_reason_code(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        payload = err.audit_payload()
        assert payload["reason_code"] == "host_bash_disabled"

    def test_payload_contains_policy_field(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        payload = err.audit_payload()
        assert payload["policy_field"] == "allow_host_bash"

    def test_payload_contains_requested_action(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        payload = err.audit_payload()
        assert payload["requested_action"] == "execute_bash"

    def test_payload_contains_requested_path_when_present(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        payload = err.audit_payload()
        assert payload["requested_path"] == "/tmp/bad"

    def test_payload_contains_allowed_boundary_when_present(self):
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        payload = err.audit_payload()
        assert payload["allowed_boundary"] == "output_only"

    def test_payload_omits_none_fields(self):
        err = PolicyDeniedError(
            reason_code="tool_calls_disabled",
            policy_field="tool_execution_mode",
            requested_action="tool_call",
        )
        payload = err.audit_payload()
        assert "requested_path" not in payload
        assert "allowed_boundary" not in payload

    def test_payload_is_json_serializable(self):
        import json
        err = PolicyDeniedError(
            reason_code="write_outside_allowed_roots",
            policy_field="sandbox.filesystem_access",
            requested_action="write",
            requested_path="/tmp/bad",
            allowed_boundary="output_only",
        )
        dumped = json.dumps(err.audit_payload())
        assert "write_outside_allowed_roots" in dumped

    def test_payload_is_stable_across_calls(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        assert err.audit_payload() == err.audit_payload()


# ---------------------------------------------------------------------------
# Is an Exception subclass
# ---------------------------------------------------------------------------

class TestExceptionContract:
    def test_is_exception(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(PolicyDeniedError) as exc_info:
            raise PolicyDeniedError(
                reason_code="tool_calls_disabled",
                policy_field="tool_execution_mode",
                requested_action="tool_call",
            )
        assert exc_info.value.reason_code == "tool_calls_disabled"

    def test_message_is_str(self):
        err = PolicyDeniedError(
            reason_code="host_bash_disabled",
            policy_field="allow_host_bash",
            requested_action="execute_bash",
        )
        assert isinstance(str(err), str)


# ---------------------------------------------------------------------------
# MM06 Step 4 refinement — denial contract completeness
# ---------------------------------------------------------------------------

class TestReasonCodeDocumentation:
    """All reason codes used at runtime must be present in the PolicyDeniedError docstring."""

    _KNOWN_REASON_CODES = {
        "host_bash_disabled",
        "write_outside_allowed_roots",
        "network_access_disallowed",
        "tool_calls_disabled",
        "tool_unclassified",
        "invalid_destination_type",
    }

    def test_all_reason_codes_in_docstring(self):
        """Every known reason code must appear in the PolicyDeniedError docstring."""
        doc = PolicyDeniedError.__doc__ or ""
        missing = [rc for rc in self._KNOWN_REASON_CODES if rc not in doc]
        assert missing == [], f"Reason code(s) missing from PolicyDeniedError docstring: {missing}"

    def test_invalid_destination_type_constructable(self):
        """invalid_destination_type must be a valid reason code at construction time."""
        err = PolicyDeniedError(
            reason_code="invalid_destination_type",
            policy_field="sandbox.network_access",
            requested_action="tool_dispatch:BrokenTool",
        )
        assert err.reason_code == "invalid_destination_type"
        assert err.policy_field == "sandbox.network_access"
