"""Google Gemini CLI backend.

Uses stdin for prompt delivery with ``-p ""``.  The ``-p`` flag
triggers headless mode while stdin provides the actual prompt text.
"""

from __future__ import annotations

import json
import logging

from .banners import looks_like_quota_banner
from .base import Backend
from .jsonl import parse_jsonl_last_result, strip_markdown_fences
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode

log = logging.getLogger("autoresearch")


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
            if looks_like_quota_banner(stdout):
                log.warning("Gemini CLI returned a quota/rate-limit banner instead of JSON; treating as error.")
                log.debug("Dropped (banner) stdout: %r", stdout[:500])
                return AgentResponse(text="", cost_usd=0.0, is_error=True)
            log.warning("Gemini CLI returned non-JSON stdout (%d chars); passing through as fenced text.", len(stdout))
            return AgentResponse(text=strip_markdown_fences(stdout), cost_usd=0.0, is_error=False)

        if isinstance(payload, dict):
            in_tok, out_tok = self._extract_tokens(payload)
            text = payload.get("response", payload.get("result", ""))
            return AgentResponse(
                text=strip_markdown_fences(text),
                cost_usd=0.0,
                is_error=payload.get("error") is not None,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )

        return parse_jsonl_last_result(stdout, cost_key="cost_usd")

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
