"""Helpers for aggregating runtime retry and tool-loop telemetry."""

from __future__ import annotations

from typing import Any

from .backends import AgentResponse


def accumulate_tool_loop(
    summary: dict[str, Any],
    tool_trace: list[dict[str, Any]],
    response: AgentResponse,
    *,
    backend_name: str = "",
) -> None:
    """Accumulate normalized tool-loop observability from a response."""
    if not isinstance(response.raw, dict):
        return
    raw_summary = response.raw.get("tool_loop", {})
    if not isinstance(raw_summary, dict) or not raw_summary:
        return
    name = str(raw_summary.get("backend") or backend_name or "unknown")
    summary["runs"] += 1
    summary["tool_calls"] += int(raw_summary.get("tool_calls", 0) or 0)
    summary["tool_failures"] += int(raw_summary.get("tool_failures", 0) or 0)
    entry = summary["per_backend"].setdefault(
        name,
        {"runs": 0, "tool_calls": 0, "tool_failures": 0, "tools": {}},
    )
    entry["runs"] += 1
    entry["tool_calls"] += int(raw_summary.get("tool_calls", 0) or 0)
    entry["tool_failures"] += int(raw_summary.get("tool_failures", 0) or 0)
    trace = response.raw.get("tool_trace", [])
    if not isinstance(trace, list):
        return
    for item in trace:
        if not isinstance(item, dict):
            continue
        tool_trace.append(item)
        tool_name = str(item.get("tool_name") or "unknown")
        failed = item.get("status") != "success"
        per_tool = summary["per_tool"].setdefault(
            tool_name,
            {"calls": 0, "failures": 0},
        )
        per_tool["calls"] += 1
        per_tool["failures"] += int(failed)
        backend_tool = entry["tools"].setdefault(tool_name, {"calls": 0, "failures": 0})
        backend_tool["calls"] += 1
        backend_tool["failures"] += int(failed)


def accumulate_retries(
    summary: dict[str, Any],
    response: AgentResponse,
    *,
    backend_name: str = "",
) -> None:
    """Accumulate retry counts from a backend response."""
    if not isinstance(response.raw, dict):
        return
    attempts = int(response.raw.get("retry_attempts", 0) or 0)
    if attempts <= 0:
        return
    name = str(backend_name or getattr(response, "backend", "") or "unknown")
    summary["total_retries"] += attempts
    summary["per_backend"][name] = summary["per_backend"].get(name, 0) + attempts
    category_entry = summary["per_backend_category"].setdefault(name, {})
    retry_summary = response.raw.get("retry_summary", {})
    if not isinstance(retry_summary, dict):
        return
    categories = retry_summary.get("categories", {})
    if not isinstance(categories, dict):
        return
    for category, count in categories.items():
        value = int(count or 0)
        summary["per_category"][category] = summary["per_category"].get(category, 0) + value
        category_entry[category] = category_entry.get(category, 0) + value
