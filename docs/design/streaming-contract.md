# Streaming Contract Design

This document originally defined the streaming rollout before runtime support
landed. It now serves two purposes:

1. document the **current implemented streaming contract**
2. document the **still-deferred future work**, especially streaming combined
   with tool-calling

## Why this needs a design first

Streaming is not just a transport optimization. It changes:

- backend invocation APIs
- error handling
- moderation and audit behavior
- report generation semantics
- interactive UX expectations

So the right question is not "can provider X stream?" but:

**what streaming behavior can this project normalize reliably across providers?**

## Verified provider surface

Based on current official docs:

- OpenAI Responses supports streaming with `stream=true`
- GitHub Models supports streaming chat completions
- Gemini supports streaming `generateContent`
- Bedrock supports `ConverseStream`
- Anthropic supports streaming Messages
- Bedrock CLI does **not** support streaming operations

Sources:

- OpenAI streaming responses: https://platform.openai.com/docs/guides/streaming-responses
- GitHub Models inference: https://docs.github.com/en/rest/models/inference
- Gemini streaming: https://ai.google.dev/gemini-api/docs/system-instructions
- Bedrock ConverseStream: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html
- Anthropic streaming messages: https://docs.anthropic.com/en/api/messages-streaming

## Current implemented contract

Streaming is already implemented with this scope:

- `CallOptions.stream`
- normalized `StreamEvent`
- backend `invoke_stream(...)` paths for:
  - `claude-api`
  - `codex-api`
  - `gemini-api`
  - `litellm-api`
  - `copilot-api`
  - `bedrock-api`
- orchestration support in `run` research-phase calls only

Current behavior:

- streaming is **opt-in**
- streaming is **interactive-first**
- streamed text is **operator feedback only**
- the **final parsed backend response remains authoritative**
- hypothesis / judge / synthesis do **not** stream
- `refine` / `plan` do **not** currently integrate workflow-level streaming

## Minimal normalized runtime contract

Implemented normalized contract:

- add `stream: bool = False` to `CallOptions`
- add a separate invocation path, for example:
  - `invoke_stream(...) -> Iterator[StreamEvent]`
- keep current `invoke(...) -> AgentResponse` unchanged
- use streaming only in interactive contexts first

### Minimal normalized event model

```python
@dataclass(frozen=True)
class StreamEvent:
    type: str               # start | text_delta | tool_call_delta | error | completed
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
```

The project currently normalizes only:

- `start`
- `text_delta`
- `error`
- `completed`

Everything else can remain provider-specific in `raw`.

## What is still intentionally deferred

### Streaming + tool-calling together

Do **not** include this in the first implementation slice.

Why:

- OpenAI uses semantic streaming events
- Bedrock and Anthropic have different event structures
- Gemini and GitHub Models have different chunk shapes
- partial tool-call argument assembly is harder than plain text streaming

### Structured-output-first streaming semantics

Still deferred because:

- different providers surface structured deltas differently
- final schema-valid payloads are easier to trust than partial ones

## Workflow policy

### `run`

Streaming should be optional and initially limited to:

- interactive progress display
- not scoring
- not artifact persistence

The authoritative result should still come from the final normalized response.

### `refine` / `plan`

Streaming is only worth enabling for interactive mode.
The persisted artifact should still come from the final completed response.

## Moderation and reliability policy

Streaming increases risk because partial content may be shown before:

- final completion
- final refusal
- postprocessing

So the first rollout should:

- treat streamed text as provisional
- avoid writing streamed deltas directly to final artifacts
- use the final non-stream-assembled normalized response as source of truth

## Historical rollout order

The early rollout plan was:

1. add `stream` to `CallOptions`
2. introduce `StreamEvent`
3. implement one transport seam in `base_api.py`
4. support first:
   - `codex-api`
   - `litellm-api`
   - `copilot-api`
5. then evaluate:
   - `claude-api`
   - `gemini-api`
   - `bedrock-api`
6. defer CLI streaming

That rollout is now complete for the current API backend set.

## Why this provider order still mattered

- OpenAI-compatible APIs are the easiest to normalize first
- the project already has shared OpenAI-compatible transport code
- Bedrock and Anthropic have more specialized streaming event shapes

## Current recommendation

Keep streaming:

- **opt-in**
- **interactive-first**
- **text-delta only**

Still do **not** combine streaming and function-tool execution yet.
