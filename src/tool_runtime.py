"""Runtime helper for the first normalized API function-tool slice."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .backends import AgentResponse, Backend, CallOptions, ToolResult

TRACE_ARG_STRING_PREVIEW_CHARS = 120
TRACE_OUTPUT_PREVIEW_CHARS = 240
TRACE_SEQUENCE_PREVIEW_ITEMS = 5
TRACE_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
    }
)


def run_function_tool_loop(
    backend: Backend,
    prompt: str,
    opts: CallOptions,
    *,
    timeout: int,
    tool_registry: dict[str, Callable[[dict[str, Any]], Any]],
) -> AgentResponse:
    """Run a bounded non-streaming function-tool loop for compatible backends."""
    current_input: Any = prompt
    conversation_items: list[dict[str, Any]] | None = None
    summary = {
        "backend": backend.name,
        "turns": 0,
        "tool_calls": 0,
        "tool_failures": 0,
    }
    tool_trace: list[dict[str, Any]] = []

    for _ in range(max(1, opts.max_turns)):
        summary["turns"] += 1
        response = backend.invoke(current_input, opts, timeout=timeout)
        if response.is_error:
            response.raw["tool_loop"] = dict(summary)
            response.raw["tool_trace"] = list(tool_trace)
            return response

        extract_calls = getattr(backend, "extract_function_tool_calls", None)
        tool_calls = extract_calls(response.raw) if callable(extract_calls) else []
        if not tool_calls:
            response.raw["tool_loop"] = dict(summary)
            response.raw["tool_trace"] = list(tool_trace)
            return response
        summary["tool_calls"] += len(tool_calls)

        tool_outputs: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            result = _execute_tool_call(tool_call.name, tool_call.call_id, tool_call.arguments_json, tool_registry)
            if result.is_error:
                summary["tool_failures"] += 1
                tool_trace.append(
                    {
                        "backend": backend.name,
                        "turn": summary["turns"],
                        "tool_name": tool_call.name,
                        "call_id": tool_call.call_id,
                        "status": "error",
                        "provider_code": result.raw.get("provider_code", "tool_execution_failed"),
                        "arguments_summary": result.raw.get("arguments_summary", {}),
                        "output_summary": _summarize_output_text(result.output),
                    }
                )
                return AgentResponse(
                    text="",
                    cost_usd=0.0,
                    is_error=True,
                    raw={
                        "error": {
                            "category": "tool_execution",
                            "message": result.output,
                            "provider_code": result.raw.get("provider_code", "tool_execution_failed"),
                            "retryable": False,
                        },
                        "payload": result.raw,
                        "tool_loop": dict(summary),
                        "tool_trace": list(tool_trace),
                    },
                )
            tool_trace.append(
                {
                    "backend": backend.name,
                    "turn": summary["turns"],
                    "tool_name": tool_call.name,
                    "call_id": result.call_id,
                    "status": "success",
                    "arguments_summary": result.raw.get("arguments_summary", {}),
                    "output_summary": result.raw.get("output_summary", _summarize_output_text(result.output)),
                }
            )
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": result.call_id,
                    "output": result.output,
                }
            )

        build_followup = getattr(backend, "build_tool_followup_input", None)
        if callable(build_followup):
            current_input = build_followup(prompt, response.raw, tool_outputs)
            continue

        if conversation_items is None:
            conversation_items = list(response.raw.get("output", []))
        else:
            conversation_items.extend(response.raw.get("output", []))
        conversation_items.extend(tool_outputs)
        current_input = conversation_items

    return AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=True,
        raw={
            "error": {
                "category": "tool_execution",
                "message": "Tool-calling loop exhausted max_turns before producing a final answer.",
                "provider_code": "max_turns_exhausted",
                "retryable": False,
            },
            "payload": {},
            "tool_loop": dict(summary),
            "tool_trace": list(tool_trace),
        },
    )


def _execute_tool_call(
    name: str,
    call_id: str,
    arguments_json: str,
    tool_registry: dict[str, Callable[[dict[str, Any]], Any]],
) -> ToolResult:
    """Execute one function tool call from the normalized registry."""
    arguments_summary = _summarize_arguments_json(arguments_json)
    handler = tool_registry.get(name)
    if handler is None:
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Unknown tool '{name}'.",
            is_error=True,
            raw={"provider_code": "unknown_tool", "arguments_summary": arguments_summary},
        )
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Invalid tool arguments for '{name}': {exc}",
            is_error=True,
            raw={"provider_code": "invalid_arguments", "arguments_summary": arguments_summary},
        )

    try:
        output = handler(arguments)
    except Exception as exc:  # pragma: no cover - exercised by behavior contract, not branch shape
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Tool '{name}' failed: {exc}",
            is_error=True,
            raw={"provider_code": "tool_handler_failed", "arguments_summary": arguments_summary},
        )

    if isinstance(output, str):
        rendered = output
    else:
        rendered = json.dumps(output)
    return ToolResult(
        call_id=call_id,
        name=name,
        output=rendered,
        raw={
            "arguments_summary": arguments_summary,
            "output_summary": _summarize_output_text(rendered),
        },
    )


def _summarize_arguments_json(arguments_json: str) -> dict[str, Any]:
    """Return a safe, redacted preview of tool-call arguments."""
    try:
        parsed = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {
            "_invalid_json": True,
            "_chars": len(arguments_json or ""),
        }
    return _summarize_trace_value(parsed)


def _summarize_trace_value(value: Any, *, key_name: str = "") -> Any:
    """Summarize nested tool trace data without leaking secrets or huge blobs."""
    if key_name and key_name.lower() in TRACE_SENSITIVE_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(key): _summarize_trace_value(item, key_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        preview = [_summarize_trace_value(item) for item in value[:TRACE_SEQUENCE_PREVIEW_ITEMS]]
        if len(value) > TRACE_SEQUENCE_PREVIEW_ITEMS:
            preview.append(f"... ({len(value) - TRACE_SEQUENCE_PREVIEW_ITEMS} more items)")
        return preview
    if isinstance(value, tuple):
        return _summarize_trace_value(list(value))
    if isinstance(value, str):
        return _truncate_string(value, TRACE_ARG_STRING_PREVIEW_CHARS)
    return value


def _summarize_output_text(output: str) -> dict[str, Any]:
    """Return safe output preview metadata for tool trace entries."""
    return {
        "preview": _truncate_string(output, TRACE_OUTPUT_PREVIEW_CHARS),
        "chars": len(output),
        "truncated": len(output) > TRACE_OUTPUT_PREVIEW_CHARS,
    }


def _truncate_string(value: str, limit: int) -> str:
    """Truncate long strings for trace artifacts."""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}…"
