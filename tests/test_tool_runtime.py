"""Tests for the first normalized API tool-calling runtime slice."""

import json

from src.backends import AgentResponse, get_backend
from src.backends.types import CallOptions, ToolDefinition
from src.tool_runtime import run_function_tool_loop


def test_run_function_tool_loop_executes_single_codex_tool_round_trip():
    backend = get_backend("codex-api")
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": [
                    {
                        "id": "fc_123",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "echo",
                        "arguments": json.dumps({"message": "hello"}),
                    }
                ]
            },
        ),
        AgentResponse(
            text="Tool said hello",
            cost_usd=0.0,
            is_error=False,
            raw={"output_text": "Tool said hello"},
        ),
    ])
    backend.invoke = lambda prompt, opts, timeout=300: next(responses)
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "Tool said hello"
    assert resp.raw["tool_loop"]["tool_calls"] == 1
    assert resp.raw["tool_loop"]["turns"] == 2


def test_run_function_tool_loop_returns_error_for_unknown_tool():
    backend = get_backend("codex-api")
    backend.invoke = lambda prompt, opts, timeout=300: AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=False,
        raw={
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "missing_tool",
                    "arguments": "{}",
                }
            ]
        },
    )
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=2,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: "unused"},
    )

    assert resp.is_error is True
    assert resp.raw["error"]["category"] == "tool_execution"
    assert resp.raw["tool_loop"]["tool_failures"] == 1


def test_run_function_tool_loop_returns_error_for_invalid_json_arguments():
    backend = get_backend("codex-api")
    backend.invoke = lambda prompt, opts, timeout=300: AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=False,
        raw={
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "echo",
                    "arguments": "{bad json",
                }
            ]
        },
    )
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=2,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: "unused"},
    )

    assert resp.is_error is True
    assert resp.raw["error"]["category"] == "tool_execution"
    assert resp.raw["error"]["provider_code"] == "invalid_arguments"
    assert resp.raw["tool_loop"]["tool_failures"] == 1


def test_run_function_tool_loop_returns_error_when_max_turns_exhausted():
    backend = get_backend("codex-api")
    backend.invoke = lambda prompt, opts, timeout=300: AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=False,
        raw={
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "echo",
                    "arguments": "{}",
                }
            ]
        },
    )
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=1,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: "ok"},
    )

    assert resp.is_error is True
    assert resp.raw["error"]["provider_code"] == "max_turns_exhausted"
    assert resp.raw["tool_loop"]["turns"] == 1


def test_run_function_tool_loop_executes_single_litellm_tool_round_trip():
    backend = get_backend("litellm-api")
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": [
                    {
                        "id": "fc_123",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "echo",
                        "arguments": json.dumps({"message": "hello"}),
                    }
                ]
            },
        ),
        AgentResponse(
            text="LiteLLM final",
            cost_usd=0.0,
            is_error=False,
            raw={"output_text": "LiteLLM final"},
        ),
    ])
    backend.invoke = lambda prompt, opts, timeout=300: next(responses)
    opts = CallOptions(
        model="openai/gpt-4.1-mini",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "LiteLLM final"


def test_run_function_tool_loop_executes_single_copilot_tool_round_trip():
    backend = get_backend("copilot-api")
    seen_prompts: list[object] = []
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "echo",
                                        "arguments": json.dumps({"message": "hello"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        ),
        AgentResponse(
            text="Copilot final",
            cost_usd=0.0,
            is_error=False,
            raw={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Copilot final",
                        }
                    }
                ]
            },
        ),
    ])

    def invoke(prompt, opts, timeout=300):
        seen_prompts.append(prompt)
        return next(responses)

    backend.invoke = invoke
    opts = CallOptions(
        model="openai/gpt-4.1",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "Copilot final"
    second_prompt = seen_prompts[1]
    assert second_prompt[-1] == {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": "echo:hello",
    }


def test_run_function_tool_loop_executes_single_claude_tool_round_trip():
    backend = get_backend("claude-api")
    seen_prompts: list[object] = []
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "echo",
                        "input": {"message": "hello"},
                    }
                ],
                "stop_reason": "tool_use",
            },
        ),
        AgentResponse(
            text="Claude final",
            cost_usd=0.0,
            is_error=False,
            raw={
                "content": [{"type": "text", "text": "Claude final"}],
            },
        ),
    ])

    def invoke(prompt, opts, timeout=300):
        seen_prompts.append(prompt)
        return next(responses)

    backend.invoke = invoke
    opts = CallOptions(
        model="claude-sonnet-4-5",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
        tool_choice="required",
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "Claude final"
    second_prompt = seen_prompts[1]
    assert second_prompt[-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "echo:hello",
            }
        ],
    }


def test_run_function_tool_loop_executes_single_gemini_tool_round_trip():
    backend = get_backend("gemini-api")
    seen_prompts: list[object] = []
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "echo",
                                        "args": {"message": "hello"},
                                    }
                                }
                            ],
                        }
                    }
                ]
            },
        ),
        AgentResponse(
            text="Gemini final",
            cost_usd=0.0,
            is_error=False,
            raw={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Gemini final"}],
                        }
                    }
                ]
            },
        ),
    ])

    def invoke(prompt, opts, timeout=300):
        seen_prompts.append(prompt)
        return next(responses)

    backend.invoke = invoke
    opts = CallOptions(
        model="gemini-2.5-flash",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
        tool_choice="required",
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "Gemini final"
    second_prompt = seen_prompts[1]
    assert second_prompt[-1] == {
        "role": "tool",
        "parts": [
            {
                "functionResponse": {
                    "name": "echo",
                    "response": {"output": "echo:hello"},
                }
            }
        ],
    }


def test_run_function_tool_loop_executes_single_bedrock_tool_round_trip():
    backend = get_backend("bedrock-api")
    seen_prompts: list[object] = []
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": {
                    "message": {
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "toolu_123",
                                    "name": "echo",
                                    "input": {"message": "hello"},
                                }
                            }
                        ]
                    }
                },
                "stopReason": "tool_use",
                "messages": [
                    {"role": "user", "content": [{"text": "Say hi"}]},
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "toolu_123",
                                    "name": "echo",
                                    "input": {"message": "hello"},
                                }
                            }
                        ],
                    },
                ],
            },
        ),
        AgentResponse(
            text="Bedrock final",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": {
                    "message": {
                        "content": [{"text": "Bedrock final"}],
                    }
                }
            },
        ),
    ])

    def invoke(prompt, opts, timeout=300):
        seen_prompts.append(prompt)
        return next(responses)

    backend.invoke = invoke
    opts = CallOptions(
        model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        max_turns=3,
        tools=(ToolDefinition(type="function", name="echo"),),
        tool_choice="required",
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={"echo": lambda args: f"echo:{args['message']}"},
    )

    assert resp.text == "Bedrock final"
    second_prompt = seen_prompts[1]
    assert second_prompt[-1] == {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": "toolu_123",
                    "content": [{"text": "echo:hello"}],
                }
            }
        ],
    }


def test_run_function_tool_loop_executes_multiple_tool_calls_in_one_turn():
    backend = get_backend("codex-api")
    seen_prompts: list[object] = []
    responses = iter([
        AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": [
                    {
                        "id": "fc_1",
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "echo",
                        "arguments": json.dumps({"message": "hello"}),
                    },
                    {
                        "id": "fc_2",
                        "type": "function_call",
                        "call_id": "call_2",
                        "name": "sum_numbers",
                        "arguments": json.dumps({"numbers": [1, 2, 3]}),
                    },
                ]
            },
        ),
        AgentResponse(
            text="All tools completed",
            cost_usd=0.0,
            is_error=False,
            raw={"output_text": "All tools completed"},
        ),
    ])

    def invoke(prompt, opts, timeout=300):
        seen_prompts.append(prompt)
        return next(responses)

    backend.invoke = invoke
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=3,
        tools=(
            ToolDefinition(type="function", name="echo"),
            ToolDefinition(type="function", name="sum_numbers"),
        ),
    )

    resp = run_function_tool_loop(
        backend,
        "Say hi",
        opts,
        timeout=30,
        tool_registry={
            "echo": lambda args: f"echo:{args['message']}",
            "sum_numbers": lambda args: {"total": sum(args["numbers"])},
        },
    )

    assert resp.text == "All tools completed"
    second_prompt = seen_prompts[1]
    assert isinstance(second_prompt, list)
    assert second_prompt[-2:] == [
        {"type": "function_call_output", "call_id": "call_1", "output": "echo:hello"},
        {"type": "function_call_output", "call_id": "call_2", "output": '{"total": 6}'},
    ]


def test_run_function_tool_loop_returns_error_for_tool_handler_failure():
    backend = get_backend("codex-api")
    backend.invoke = lambda prompt, opts, timeout=300: AgentResponse(
        text="",
        cost_usd=0.0,
        is_error=False,
        raw={
            "output": [
                {
                    "id": "fc_123",
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "explode",
                    "arguments": "{}",
                }
            ]
        },
    )
    opts = CallOptions(
        model="gpt-5.4",
        max_turns=2,
        tools=(ToolDefinition(type="function", name="explode"),),
    )

    resp = run_function_tool_loop(
        backend,
        "Boom",
        opts,
        timeout=30,
        tool_registry={"explode": lambda args: (_ for _ in ()).throw(RuntimeError("boom"))},
    )

    assert resp.is_error is True
    assert resp.raw["error"]["provider_code"] == "tool_handler_failed"
    assert resp.raw["tool_loop"]["tool_failures"] == 1
