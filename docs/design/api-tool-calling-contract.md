# API Tool-Calling Contract Design

This document defines the decision framework for API tool-calling support.

## Why this should be last

Tool-calling is the largest remaining contract expansion because it touches:

- prompt/runtime semantics
- provider capability mapping
- tool schema normalization
- tool result plumbing
- partial failure handling
- streaming semantics

So the project should not jump directly from "API adapters exist" to
"cross-provider tool use works."

## Verified provider surface

Current official provider surfaces indicate that tool/function calling exists in
some form across major APIs, but **not symmetrically**:

- OpenAI Responses supports tools and tool choice
- GitHub Models supports functions in the inference API
- Gemini supports function calling
- Bedrock Converse supports tool use
- Anthropic supports MCP/tool-related features in Messages API

Sources:

- OpenAI Responses API: https://platform.openai.com/docs/api-reference/responses/retrieve
- GitHub Models inference: https://docs.github.com/en/rest/models/inference
- Gemini API docs: https://ai.google.dev/api/rest/generativelanguage/CitationMetadata
- Bedrock tool use: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html
- Anthropic Messages/API docs: https://docs.anthropic.com/en/api/messages

## Recommendation: do not normalize all tools at once

The project should treat API tool-calling as a phased feature.

## Phase 1 — function tools only

First supported normalized tool type:

- `function`

Do **not** start with:

- hosted built-in tools
- MCP tools
- provider-specific server-side tools

Why:

- function tools are the closest thing to a shared denominator
- hosted tools vary too much by provider
- MCP support is still too provider-specific for a first normalized layer

## Proposed normalized contract

### Tool definition

```python
@dataclass(frozen=True)
class ToolDefinition:
    type: str                # currently only "function"
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
```

### Tool result

```python
@dataclass(frozen=True)
class ToolResult:
    name: str
    call_id: str = ""
    output: str = ""
    is_error: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
```

### Call options

Future extension candidate:

```python
tools: tuple[ToolDefinition, ...] = ()
tool_choice: str = "auto"   # auto | required | none
```

## Capability policy

Only backends that can reliably map the normalized contract should set:

- `supports_tools = true`

This should be project-truth, not provider-marketing-truth.

### Recommended initial support order

1. `codex-api`
2. `litellm-api` *(only when routed provider behavior is constrained enough)*
3. `copilot-api`

Defer initially:

- `bedrock-api`
- `claude-api`
- `gemini-api`

Not because they lack tool surfaces, but because the project will get faster,
cleaner wins by starting with the OpenAI-compatible path.

## Why aggregators are tricky

Aggregators may:

- route to different providers with different tool semantics
- partially support tool choice
- alter tool-call event shapes
- require model-specific constraints

So aggregator support should eventually be per-instance validated, not assumed
globally from the adapter name alone.

## Runtime policy

### First implementation should be non-streaming

The safest first contract is:

- model returns a normalized tool-call request
- runtime executes the tool
- runtime sends tool result back through a follow-up request
- final answer is returned after the tool round-trip

Do **not** combine first-pass tool-calling with streaming.

## Failure policy

Tool-call failures need their own normalization:

- unsupported tool schema
- tool execution failure
- malformed tool arguments
- provider refusal / fallback to text

This is another reason to keep v1 scope narrow.

## Recommended rollout

### Step 1

Write tests and transport contract for function tools on one OpenAI-compatible
backend.

### Step 2

Add a tool-execution loop in the orchestrator/runtime, bounded by existing
`max_turns`.

### Step 3

Add capability enforcement so unsupported adapters strip or reject tool config.

### Step 4

Only then evaluate aggregators and non-OpenAI-native mappings.

## Current implementation status

The first implementation slice is now in place with the following scope:

- function tools only
- non-streaming only
- explicit backend support only
- currently enabled for `claude-api`, `codex-api`, `gemini-api`, `litellm-api`, `copilot-api`, and `bedrock-api`

What landed:

- normalized tool dataclasses
- `CallOptions.tools` and `CallOptions.tool_choice`
- capability flag: `supports_function_tools`
- OpenAI Responses request shaping for function tools
- normalized function-call extraction from Responses payloads
- a bounded runtime tool loop for explicit tool registries
- orchestrator wiring for explicit tool-enabled calls
- multi-tool execution in a single model turn
- normalized handler/argument/max-turn failure behavior
- invalid `tool_choice` normalization back to `auto`
- tool-loop observability in metrics/dashboard artifacts

What is still intentionally deferred:

- streaming + tool-calling together
- hosted tools / MCP tools / provider-native non-function tools

## Recommendation

Keep the next step narrow too:

- extend to one more OpenAI-compatible adapter only after runtime behavior is stable
- do not mix streaming and tools yet
- keep CLI `allowed_tools` separate from normalized API function tools
