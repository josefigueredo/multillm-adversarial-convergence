"""Runtime helper for the first normalized API function-tool slice."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .backends import AgentResponse, Backend, CallOptions, ToolResult


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
    handler = tool_registry.get(name)
    if handler is None:
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Unknown tool '{name}'.",
            is_error=True,
            raw={"provider_code": "unknown_tool"},
        )
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Invalid tool arguments for '{name}': {exc}",
            is_error=True,
            raw={"provider_code": "invalid_arguments", "arguments_json": arguments_json},
        )

    try:
        output = handler(arguments)
    except Exception as exc:  # pragma: no cover - exercised by behavior contract, not branch shape
        return ToolResult(
            call_id=call_id,
            name=name,
            output=f"Tool '{name}' failed: {exc}",
            is_error=True,
            raw={"provider_code": "tool_handler_failed"},
        )

    if isinstance(output, str):
        rendered = output
    else:
        rendered = json.dumps(output)
    return ToolResult(call_id=call_id, name=name, output=rendered)
