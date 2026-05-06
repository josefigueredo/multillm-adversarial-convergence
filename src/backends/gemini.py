"""Google Gemini CLI backend.

Uses stdin for prompt delivery with ``-p ""``.  The ``-p`` flag
triggers headless mode while stdin provides the actual prompt text.
"""

from __future__ import annotations

import json

from .base import Backend
from .jsonl import parse_jsonl_last_result
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode


class GeminiBackend(Backend):

    name = "gemini-cli"
    capabilities = BackendCapabilities(
        transport="cli",
        provider_kind="direct",
        default_model="gemini-2.5-flash",
    )

    def cli_executable(self) -> str:
        return "gemini"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.STDIN

    def build_command(self, opts: CallOptions) -> list[str]:
        cmd = ["gemini", "-p", ""]
        if opts.model:
            cmd.extend(["--model", opts.model])
        cmd.extend(["--output-format", "json"])
        if opts.allowed_tools:
            cmd.append("--yolo")
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return AgentResponse(text=self._strip_markdown_fences(stdout), cost_usd=0.0, is_error=False)

        if isinstance(payload, dict):
            in_tok, out_tok = self._extract_tokens(payload)
            text = payload.get("response", payload.get("result", ""))
            return AgentResponse(
                text=self._strip_markdown_fences(text),
                cost_usd=0.0,
                is_error=payload.get("error") is not None,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )

        return parse_jsonl_last_result(stdout, cost_key="cost_usd")

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove a single outer ```lang\\n...\\n``` markdown fence.

        Gemini models wrap code-shaped output in markdown fences even when
        the prompt explicitly forbids it. Strip the outer fence at the
        adapter layer so downstream JSON parsing and synthesis writers see
        clean content. Inner fences and prose without fences are unchanged.
        """
        text = text.strip()
        if not text.startswith("```"):
            return text
        first_newline = text.find("\n")
        if first_newline == -1:
            return text
        body = text[first_newline + 1:]
        if body.endswith("```"):
            body = body[:-3]
        return body.strip()

    @staticmethod
    def _extract_tokens(payload: dict) -> tuple[int, int]:
        """Extract token counts from Gemini's stats object."""
        stats = payload.get("stats", {})
        models = stats.get("models", {})
        in_tok = 0
        out_tok = 0
        for model_stats in models.values():
            tokens = model_stats.get("tokens", {})
            in_tok += tokens.get("input", 0)
            out_tok += tokens.get("candidates", 0)
        return in_tok, out_tok
