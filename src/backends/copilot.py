"""GitHub Copilot CLI backend.

Prompts are passed as the ``-p`` argument value. For long prompts,
a tempfile fallback is used.  Budget caps are not available.
"""

from __future__ import annotations

import json
import logging

from .base import Backend
from .jsonl import parse_jsonl_last_result, strip_markdown_fences
from .types import AgentResponse, BackendCapabilities, CallOptions, PromptMode

log = logging.getLogger("autoresearch")


class CopilotBackend(Backend):

    name = "copilot-cli"
    capabilities = BackendCapabilities(
        transport="cli",
        provider_kind="direct",
        default_model="gpt-4.1",
    )

    def cli_executable(self) -> str:
        return "copilot"

    def prompt_mode(self) -> PromptMode:
        return PromptMode.ARGUMENT

    def build_command(self, opts: CallOptions) -> list[str]:
        # NOTE: -p takes the prompt as its value.  The base class
        # appends the prompt text as the LAST argument, so we must
        # NOT put other flags between -p and the prompt.  We put -p
        # last (before the prompt is appended by invoke()).
        cmd = ["copilot"]
        if opts.model:
            cmd.extend(["--model", opts.model])
        cmd.extend(["--output-format", "json", "--silent", "--no-ask-user"])
        if opts.allowed_tools:
            cmd.append("--allow-all")
        cmd.append("--autopilot")
        if opts.max_turns > 0:
            cmd.extend(["--max-autopilot-continues", str(opts.max_turns)])
        cmd.append("-p")
        return cmd

    def parse_response(self, stdout: str) -> AgentResponse:
        """Parse Copilot JSONL output.

        Three extraction paths in priority order:

        1. **``session.task_complete.data.summary``** — when Copilot's
           autopilot agent runs to completion, the model delivers its
           structured final answer through the ``task_complete`` tool, not
           through ``assistant.message``. The summary often wraps content
           in markdown code fences (especially JSON) which we strip.
        2. **Last ``assistant.message`` in the primary interaction** —
           for non-autopilot or short-circuit flows, the model puts its
           answer directly in an assistant message. We anchor on the
           first ``user.message``'s ``interactionId`` so autopilot's
           injected "you have not yet called task_complete" continuations
           (which carry fresh ``interactionId`` values) don't pollute the
           result with their "task complete, I submitted my JSON" prose.
        3. **``is_error=True``** when the output is Copilot-shaped (carries
           ``session.*`` or ``assistant.*`` events) but neither path
           yielded usable content — rate-limit, quota, or mid-session
           error. Returning the raw JSONL would feed the framework's
           hypothesis parser garbage.

        Non-Copilot-shaped output (test fixtures, unexpected formats)
        falls back to the generic JSONL helper.
        """
        if not stdout.strip():
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        lines = stdout.strip().splitlines()

        primary_interaction_id: str | None = None
        is_copilot_shaped = False
        task_complete_summary: str | None = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            event_type = obj.get("type", "")
            if event_type.startswith("session.") or event_type.startswith("assistant."):
                is_copilot_shaped = True
            if event_type == "user.message" and primary_interaction_id is None:
                primary_interaction_id = obj.get("data", {}).get("interactionId")
            if event_type == "session.task_complete":
                summary = obj.get("data", {}).get("summary", "")
                if summary:
                    task_complete_summary = summary

        if task_complete_summary:
            return AgentResponse(
                text=strip_markdown_fences(task_complete_summary),
                cost_usd=0.0,
                is_error=False,
            )

        last_text = ""
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or obj.get("type") != "assistant.message":
                continue
            data = obj.get("data", {})
            content = data.get("content", "")
            if not content:
                continue
            if primary_interaction_id is not None:
                if data.get("interactionId") != primary_interaction_id:
                    continue
            last_text = content
            break

        if last_text:
            return AgentResponse(text=last_text, cost_usd=0.0, is_error=False)

        if is_copilot_shaped:
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        return parse_jsonl_last_result(stdout, cost_key="cost_usd")
