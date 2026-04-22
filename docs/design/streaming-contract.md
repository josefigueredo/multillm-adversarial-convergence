# Streaming Contract Design

This document defines the recommended streaming contract for the project before
any runtime implementation lands.

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

## Recommended project contract

## Phase 1 — metadata only (current state)

Keep `supports_streaming` as capability metadata only.

Why:

- safe
- no contract break
- no partial-output persistence problems

## Phase 2 — opt-in text streaming for interactive use

Recommended first runtime contract:

- add `stream: bool = False` to `CallOptions`
- add a separate invocation path, for example:
  - `invoke_stream(...) -> Iterator[StreamEvent]`
- keep current `invoke(...) -> AgentResponse` unchanged
- only use streaming in interactive contexts first

### Minimal normalized event model

```python
@dataclass(frozen=True)
class StreamEvent:
    type: str               # start | text_delta | tool_call_delta | error | completed
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
```

The project should normalize only:

- `start`
- `text_delta`
- `error`
- `completed`

Everything else can remain provider-specific in `raw`.

## Phase 3 — tool-call and structured-output streaming

Do **not** include this in the first implementation slice.

Why:

- OpenAI uses semantic streaming events
- Bedrock and Anthropic have different event structures
- Gemini and GitHub Models have different chunk shapes
- partial tool-call argument assembly is harder than plain text streaming

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

## Recommended implementation order

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

## Why this provider order

- OpenAI-compatible APIs are the easiest to normalize first
- the project already has shared OpenAI-compatible transport code
- Bedrock and Anthropic have more specialized streaming event shapes

## Recommendation

Implement streaming only as:

- **opt-in**
- **interactive-first**
- **text-delta only**

Anything broader in v1 would be fake simplicity.
