"""Tests for runtime telemetry aggregation helpers."""

from src.backends import AgentResponse
from src.runtime_telemetry import accumulate_retries, accumulate_tool_loop


def test_accumulate_retries_updates_backend_and_category_totals():
    summary = {
        "total_retries": 0,
        "per_backend": {},
        "per_category": {},
        "per_backend_category": {},
    }
    response = AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=False,
        raw={
            "retry_attempts": 2,
            "retry_summary": {"categories": {"rate_limit": 1, "timeout": 1}},
        },
    )

    accumulate_retries(summary, response, backend_name="litellm-api")

    assert summary["total_retries"] == 2
    assert summary["per_backend"]["litellm-api"] == 2
    assert summary["per_category"]["rate_limit"] == 1
    assert summary["per_category"]["timeout"] == 1
    assert summary["per_backend_category"]["litellm-api"]["rate_limit"] == 1


def test_accumulate_tool_loop_updates_summary_and_trace():
    summary = {
        "runs": 0,
        "tool_calls": 0,
        "tool_failures": 0,
        "per_backend": {},
        "per_tool": {},
    }
    trace: list[dict[str, object]] = []
    response = AgentResponse(
        text="ok",
        cost_usd=0.0,
        is_error=False,
        raw={
            "tool_loop": {
                "backend": "codex-api",
                "tool_calls": 2,
                "tool_failures": 1,
            },
            "tool_trace": [
                {"tool_name": "echo", "status": "success"},
                {"tool_name": "explode", "status": "error"},
            ],
        },
    )

    accumulate_tool_loop(summary, trace, response, backend_name="codex-api")

    assert summary["runs"] == 1
    assert summary["tool_calls"] == 2
    assert summary["tool_failures"] == 1
    assert summary["per_backend"]["codex-api"]["tools"]["echo"]["calls"] == 1
    assert summary["per_tool"]["explode"]["failures"] == 1
    assert len(trace) == 2
