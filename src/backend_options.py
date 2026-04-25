"""Shared backend invocation option builders."""

from __future__ import annotations

from .backends import Backend, CallOptions
from .config import ExecutionConfig, ProviderConfig


def build_call_options(
    execution: ExecutionConfig,
    *,
    provider: ProviderConfig | None = None,
    working_directory: str = "",
    sanitize_environment: bool = False,
) -> CallOptions:
    """Build normalized call options from an execution config."""
    provider = provider if isinstance(provider, ProviderConfig) else None
    model = provider.model if provider and provider.model else execution.model
    allowed_tools = provider.allowed_tools if provider and provider.allowed_tools else execution.allowed_tools
    max_turns = provider.max_turns if provider and provider.max_turns > 0 else execution.max_turns
    max_budget = (
        provider.max_budget_per_call
        if provider and provider.max_budget_per_call >= 0
        else execution.max_budget_per_call
    )
    return CallOptions(
        model=model,
        system_prompt=execution.system_prompt,
        stream=execution.stream,
        tools=(),
        tool_choice="auto",
        allowed_tools=allowed_tools,
        max_turns=max_turns,
        max_budget_usd=max_budget,
        working_directory=working_directory,
        sanitize_environment=sanitize_environment,
    )


def apply_backend_capabilities(backend: Backend, opts: CallOptions) -> CallOptions:
    """Strip unsupported options so the runtime contract is explicit."""
    normalized_tool_choice = opts.tool_choice if opts.tool_choice in {"auto", "required", "none"} else "auto"
    return CallOptions(
        model=opts.model,
        system_prompt=opts.system_prompt if backend.capabilities.supports_system_prompt else "",
        stream=opts.stream if backend.capabilities.supports_streaming else False,
        tools=opts.tools if backend.capabilities.supports_function_tools else (),
        tool_choice=normalized_tool_choice if backend.capabilities.supports_function_tools else "none",
        allowed_tools=opts.allowed_tools if backend.capabilities.supports_tools else "",
        max_turns=opts.max_turns,
        max_budget_usd=opts.max_budget_usd if backend.capabilities.supports_budget_cap else 0.0,
        json_schema=opts.json_schema if backend.capabilities.supports_json_schema else None,
        working_directory=opts.working_directory,
        sanitize_environment=opts.sanitize_environment,
        process_env=opts.process_env,
    )
