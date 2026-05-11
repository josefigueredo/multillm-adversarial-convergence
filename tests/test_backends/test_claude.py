"""Tests for src.backends.claude — ClaudeBackend."""

import json
from unittest.mock import MagicMock, patch

from src.backends.claude import ClaudeBackend
from src.backends.types import CallOptions, PromptMode


class TestClaudeBackend:
    def setup_method(self):
        self.backend = ClaudeBackend()

    def test_name(self):
        assert self.backend.name == "claude-cli"

    def test_cli_executable(self):
        assert self.backend.cli_executable() == "claude"

    def test_prompt_mode_stdin(self):
        assert self.backend.prompt_mode() == PromptMode.STDIN

    def test_capabilities(self):
        assert self.backend.capabilities.transport == "cli"
        assert self.backend.capabilities.provider_kind == "direct"
        assert self.backend.capabilities.supports_json_schema is True
        assert self.backend.capabilities.supports_budget_cap is True
        assert self.backend.capabilities.supports_rate_limit_detection is True
        assert self.backend.capabilities.default_model == "sonnet"

    def test_build_command_minimal(self):
        cmd = self.backend.build_command(CallOptions())
        assert cmd[:5] == ["claude", "-p", "-", "--output-format", "json"]

    def test_build_command_full(self):
        opts = CallOptions(
            model="opus",
            allowed_tools="WebSearch,Read",
            max_turns=5,
            max_budget_usd=0.75,
        )
        cmd = self.backend.build_command(opts)
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "opus"
        assert "--allowedTools" in cmd
        assert "--max-turns" in cmd
        assert "--max-budget-usd" in cmd

    def test_build_command_json_schema(self):
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        opts = CallOptions(json_schema=schema)
        cmd = self.backend.build_command(opts)
        assert "--json-schema" in cmd

    def test_parse_response_array(self):
        stdout = json.dumps([
            {"type": "system"},
            {"type": "result", "result": "findings", "total_cost_usd": 0.12,
             "usage": {"input_tokens": 100, "output_tokens": 50,
                       "cache_read_input_tokens": 200, "cache_creation_input_tokens": 30}},
        ])
        resp = self.backend.parse_response(stdout)
        assert resp.text == "findings"
        assert resp.cost_usd == 0.12
        assert resp.is_error is False
        assert resp.input_tokens == 330  # 100 + 200 + 30
        assert resp.output_tokens == 50

    def test_parse_response_dict(self):
        stdout = json.dumps({"result": "dict result", "cost_usd": 0.05})
        resp = self.backend.parse_response(stdout)
        assert resp.text == "dict result"

    def test_parse_response_plain_text(self):
        resp = self.backend.parse_response("not json at all")
        assert resp.text == "not json at all"

    def test_rate_limit_detection(self):
        assert ClaudeBackend._check_rate_limit("") == 0
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.95},
        }])
        assert ClaudeBackend._check_rate_limit(data) == 120

    def test_utilization_extraction(self):
        data = json.dumps([{
            "type": "rate_limit_event",
            "rate_limit_info": {"utilization": 0.73},
        }])
        assert ClaudeBackend._extract_utilization(data) == 0.73

    @patch.object(ClaudeBackend, "_run_process")
    def test_invoke_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"type": "result", "result": "hello", "total_cost_usd": 0.05},
            ]),
            stderr="",
        )
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.text == "hello"
        assert resp.is_error is False
        assert mock_run.call_args[1]["input"] == "prompt"

    @patch.object(ClaudeBackend, "_run_process")
    def test_invoke_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude-cli", timeout=10)
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.is_error is True

    @patch.object(ClaudeBackend, "_run_process")
    def test_invoke_salvages_budget_exceeded(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps([
                {"type": "result", "result": "partial result", "total_cost_usd": 0.50,
                 "usage": {"input_tokens": 500, "output_tokens": 200}},
            ]),
            stderr="budget exceeded",
        )
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.text == "partial result"
        assert resp.is_error is False
        assert resp.input_tokens == 500
        assert resp.output_tokens == 200

    @patch.object(ClaudeBackend, "_run_process")
    def test_invoke_does_not_salvage_usage_limit_banner(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=json.dumps([
                {"type": "result", "result": "You're out of extra usage - resets 8:30pm (UTC)"},
            ]),
            stderr="",
        )
        resp = self.backend.invoke("prompt", CallOptions(), timeout=10)
        assert resp.is_error is True
        assert resp.text == ""

    def test_parse_response_banner_on_success_is_error(self):
        """JSON-parse failure on a banner-shaped stdout must NOT be promoted
        to is_error=False findings — historically banners on rc=0 (or with
        broken JSON contract) bypassed the salvage filter and poisoned the KB.
        """
        resp = self.backend.parse_response("Rate limit exceeded for this org")
        assert resp.is_error is True
        assert resp.text == ""

    def test_parse_response_empty_stdout_is_error(self):
        resp = self.backend.parse_response("")
        assert resp.is_error is True
        assert resp.text == ""

    def test_parse_response_non_banner_plain_text_passes_through(self):
        """Genuine plain text (not banner-shaped) must still pass through;
        the salvage filter should not over-reach."""
        resp = self.backend.parse_response("Here is a real finding about caching.")
        assert resp.is_error is False
        assert resp.text == "Here is a real finding about caching."
