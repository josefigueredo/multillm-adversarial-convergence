"""Shared types for the backend abstraction layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PromptMode(Enum):
    """How the backend delivers prompts to the CLI process."""

    STDIN = "stdin"
    ARGUMENT = "argument"


class BackendTransport(str, Enum):
    """How the backend delivers calls — subprocess CLI or HTTP API.

    ``str``-mixin: string equality still works (``transport == "cli"``)
    so existing comparison sites in orchestrator/preflight/backend_options
    keep working without a sweeping rewrite. New code should prefer the
    enum members.
    """

    CLI = "cli"
    API = "api"


class ProviderKind(str, Enum):
    """Direct provider vs aggregator gateway (LiteLLM, Bedrock, OpenRouter…).

    Used by the preflight + model resolution logic to decide whether to
    translate Claude shortnames to the backend's default model.
    """

    DIRECT = "direct"
    AGGREGATOR = "aggregator"


class ToolChoice(str, Enum):
    """How the backend should treat tool use on a single call."""

    AUTO = "auto"          # model decides
    REQUIRED = "required"  # model must call a tool
    NONE = "none"          # model must NOT call a tool


@dataclass(frozen=True)
class CallOptions:
    """Options for a single CLI invocation.

    Backends map these to their CLI-specific flags.  Fields that a
    backend does not support are silently ignored.
    """

    model: str = ""
    system_prompt: str = ""
    stream: bool = False
    tools: tuple["ToolDefinition", ...] = ()
    tool_choice: ToolChoice = ToolChoice.AUTO
    allowed_tools: str = ""
    max_turns: int = 10
    max_budget_usd: float = 0.0
    json_schema: dict[str, Any] | None = None
    working_directory: str = ""
    sanitize_environment: bool = False
    process_env: dict[str, str] | None = None

    def __post_init__(self) -> None:
        # YAML loaders and ad-hoc constructions pass tool_choice as a
        # raw string; coerce to the enum so type checkers see the contract
        # while string equality at call sites keeps working via str-mixin.
        if isinstance(self.tool_choice, str) and not isinstance(self.tool_choice, ToolChoice):
            object.__setattr__(self, "tool_choice", ToolChoice(self.tool_choice))


@dataclass(frozen=True)
class AgentResponse:
    """Result of a single CLI invocation."""

    text: str
    cost_usd: float
    is_error: bool
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def with_meta(self, **meta: Any) -> "AgentResponse":
        """Return a copy with extra telemetry merged into ``raw``.

        Prefer this over in-place ``response.raw[key] = value`` — the
        in-place form defeats ``frozen=True`` and risks shared-reference
        leakage when a backend reuses the parsed payload across calls.
        """
        return AgentResponse(
            text=self.text,
            cost_usd=self.cost_usd,
            is_error=self.is_error,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            raw={**self.raw, **meta},
        )


@dataclass(frozen=True)
class StreamEvent:
    """Normalized streaming event."""

    type: str
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    """Normalized function-tool definition."""

    type: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    strict: bool = True


@dataclass(frozen=True)
class ToolCallRequest:
    """Normalized function-tool call request emitted by a backend."""

    call_id: str
    name: str
    arguments_json: str
    id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Normalized function-tool execution result."""

    call_id: str
    name: str
    output: str = ""
    is_error: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BackendCapabilities:
    """Declares what a backend supports.

    Used by the orchestrator's model translation layer to resolve
    per-backend differences without hardcoded hacks.

    Attributes:
        supports_json_schema: Can pass ``--json-schema`` for structured output.
        supports_budget_cap: Can pass per-call USD budget limits.
        supports_rate_limit_detection: Has proactive rate limit backoff.
        supports_tools: Can use agent tools (WebSearch, etc.).
        default_model: Model to use when the config model is a Claude
            shortname (e.g. ``"sonnet"``) that this backend doesn't understand.
    """

    transport: BackendTransport = BackendTransport.CLI
    provider_kind: ProviderKind = ProviderKind.DIRECT
    supports_json_schema: bool = False
    supports_budget_cap: bool = False
    supports_rate_limit_detection: bool = False
    supports_system_prompt: bool = False
    supports_streaming: bool = False
    supports_response_format: bool = False
    supports_org_routing: bool = False
    supports_function_tools: bool = False
    supports_tools: bool = True
    default_model: str = ""

    def __post_init__(self) -> None:
        # Auto-coerce string assignments to the enum types so existing
        # ``BackendCapabilities(transport="cli", provider_kind="direct")``
        # call sites in every backend keep working — but the field is now
        # typed and IDE autocomplete knows the valid values.
        if isinstance(self.transport, str) and not isinstance(self.transport, BackendTransport):
            object.__setattr__(self, "transport", BackendTransport(self.transport))
        if isinstance(self.provider_kind, str) and not isinstance(self.provider_kind, ProviderKind):
            object.__setattr__(self, "provider_kind", ProviderKind(self.provider_kind))


# Claude shortnames that non-Claude backends should translate
# to their own default_model.
CLAUDE_SHORTNAMES = frozenset({"sonnet", "opus", "haiku"})
