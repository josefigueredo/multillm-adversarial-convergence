"""Tests for src.backends.copilot — CopilotBackend."""

import json
from unittest.mock import MagicMock, patch

from src.backends.copilot import CopilotBackend
from src.backends.types import CallOptions, PromptMode


class TestCopilotBackend:
    def setup_method(self):
        self.backend = CopilotBackend()

    def test_name(self):
        assert self.backend.name == "copilot-cli"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "copilot"

    def test_prompt_mode_argument(self):
        assert self.backend.prompt_mode() == PromptMode.ARGUMENT

    def test_capabilities(self):
        assert self.backend.capabilities.default_model == "gpt-4.1"
        assert self.backend.capabilities.supports_json_schema is False
        assert self.backend.capabilities.supports_budget_cap is False

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[0] == "copilot"
        assert cmd[-1] == "-p"  # -p must be last so prompt is appended after it
        assert "--output-format" in cmd
        assert "--silent" in cmd
        assert "--no-ask-user" in cmd
        assert "--autopilot" in cmd

    def test_build_command_with_model(self):
        opts = CallOptions(model="gpt-4.1")
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "gpt-4.1"
        assert cmd[-1] == "-p"

    def test_build_command_with_tools(self):
        opts = CallOptions(allowed_tools="Read")
        cmd = self.backend.build_command(opts)
        assert "--allow-all" in cmd

    def test_build_command_with_turns(self):
        opts = CallOptions(max_turns=5)
        cmd = self.backend.build_command(opts)
        assert "--max-autopilot-continues" in cmd
        assert "5" in cmd

    def test_build_command_prompt_appended_after_p(self):
        """Verify that invoke() appends prompt right after -p."""
        cmd = self.backend.build_command(CallOptions())
        # Simulate what invoke() does for ARGUMENT mode
        cmd.append("test prompt")
        # -p should be second-to-last, prompt should be last
        assert cmd[-2] == "-p"
        assert cmd[-1] == "test prompt"

    def test_parse_response_assistant_message(self):
        lines = [
            json.dumps({"type": "session.mcp_servers_loaded", "data": {}}),
            json.dumps({
                "type": "assistant.message",
                "data": {"content": "4"},
            }),
            json.dumps({"type": "result", "sessionId": "abc", "exitCode": 0}),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == "4"
        assert resp.is_error is False

    def test_parse_response_empty(self):
        resp = self.backend.parse_response("")
        assert resp.is_error is True

    def test_parse_response_no_tokens(self):
        """Copilot doesn't report per-token usage."""
        lines = [
            json.dumps({"type": "assistant.message", "data": {"content": "hello"}}),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0

    def test_parse_response_skips_empty_content(self):
        """Copilot sometimes emits assistant.message with empty content (tool calls)."""
        lines = [
            json.dumps({
                "type": "assistant.message",
                "data": {"content": "", "toolRequests": [{"name": "task_complete"}]},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {"content": "The answer is 4."},
            }),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == "The answer is 4."

    def test_parse_response_ignores_autopilot_continuation(self):
        """Autopilot injects follow-up turns with a different interactionId.
        The real answer lives in the first interaction; ignore later ones."""
        lines = [
            json.dumps({
                "type": "user.message",
                "data": {"interactionId": "first", "content": "give me JSON"},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {"interactionId": "first", "content": '{"answer": "real"}'},
            }),
            json.dumps({
                "type": "session.info",
                "data": {"infoType": "autopilot_continuation"},
            }),
            json.dumps({
                "type": "user.message",
                "data": {"interactionId": "second", "content": "have you called task_complete?"},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {
                    "interactionId": "second",
                    "content": "Yes the task is complete, I submitted my JSON earlier.",
                },
            }),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == '{"answer": "real"}'

    def test_parse_response_takes_last_assistant_in_first_interaction(self):
        """In tool-using flows, one interaction can produce several assistant.messages.
        Take the LAST one within the original interaction (the synthesised answer)."""
        lines = [
            json.dumps({
                "type": "user.message",
                "data": {"interactionId": "X", "content": "research foo"},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {"interactionId": "X", "content": "Let me search for foo..."},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {"interactionId": "X", "content": "Final synthesis: foo is bar."},
            }),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == "Final synthesis: foo is bar."

    def test_parse_response_fallback_to_jsonl(self):
        stdout = json.dumps({"result": "fallback output"})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "fallback output"

    def test_parse_response_truncated_stream_is_error(self):
        """A truncated/corrupt JSONL stream (no recognizable Copilot shape AND
        decode failures) must NOT fall through to the generic JSONL helper
        and from there to a raw-stdout passthrough — that path used to
        promote rate-limit chunks into is_error=False findings."""
        truncated = '{"type": "session.bootstrap", "data":\n{"this is not valid json'
        resp = self.backend.parse_response(truncated)
        assert resp.is_error is True
        assert resp.text == ""

    def test_parse_response_extracts_task_complete_summary(self):
        """Copilot's autopilot agent delivers structured final answers via
        the session.task_complete tool's `data.summary` field, not via
        assistant.message. The summary often wraps content in markdown
        fences (especially JSON). task_complete takes priority over
        assistant.message because the assistant.message in this flow is
        just the model's intro prose ("Now I have findings...")."""
        lines = [
            json.dumps({"type": "session.mcp_servers_loaded", "data": {}}),
            json.dumps({
                "type": "user.message",
                "data": {"interactionId": "x", "content": "..."},
            }),
            json.dumps({
                "type": "assistant.message",
                "data": {
                    "interactionId": "x",
                    "content": "Now I have comprehensive findings. Let me formulate the JSON.",
                },
            }),
            json.dumps({
                "type": "session.task_complete",
                "data": {
                    "summary": '```json\n{"dimension":"X","questions":["Q1"]}\n```',
                    "success": True,
                },
            }),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == '{"dimension":"X","questions":["Q1"]}'
        assert resp.is_error is False

    def test_parse_response_task_complete_without_fence(self):
        """task_complete summary may also be plain text without fences."""
        lines = [
            json.dumps({"type": "user.message", "data": {"interactionId": "x"}}),
            json.dumps({
                "type": "session.task_complete",
                "data": {"summary": "plain answer text", "success": True},
            }),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.text == "plain answer text"
        assert resp.is_error is False

    def test_parse_response_copilot_shaped_no_message_returns_error(self):
        """If Copilot CLI emits its session events but no usable
        assistant.message (rate limit, quota exhausted, mid-session error),
        return is_error rather than leaking raw JSONL into the framework's
        parser. The previous behavior fell through to the generic JSONL
        helper, which returns ``stdout.strip()`` for non-matching shapes,
        causing the framework's hypothesis parser to receive raw JSONL."""
        lines = [
            json.dumps({"type": "session.mcp_servers_loaded", "data": {}}),
            json.dumps({"type": "session.tools_updated", "data": {}}),
            json.dumps({
                "type": "user.message",
                "data": {"interactionId": "x", "content": "..."},
            }),
            json.dumps({"type": "assistant.turn_start", "data": {}}),
        ]
        resp = self.backend.parse_response("\n".join(lines))
        assert resp.is_error is True
        assert resp.text == ""

    @patch.object(CopilotBackend, "_run_process")
    def test_invoke_appends_prompt_as_arg(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "type": "assistant.message",
                "data": {"content": "copilot reply"},
            }),
            stderr="",
        )
        resp = self.backend.invoke("test prompt", CallOptions(), timeout=10)
        assert resp.text == "copilot reply"
        # Verify prompt was appended as argument (not stdin)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "test prompt"
        assert cmd[-2] == "-p"
        # Stdin should NOT be used
        assert mock_run.call_args[1].get("input") is None
