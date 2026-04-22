"""API provider contracts for direct and aggregator backends.

This document defines the stable configuration contract for API-flavored
providers before implementation details drift across adapters.
"""

# API Provider Contracts

This project now treats a provider instance as:

- an **adapter identity** (`claude-api`, `copilot-api`, `bedrock-api`)
- plus an **instance contract** (`model`, `base_url`, `region`, etc.)

The goal is SIMPLE: a role points to a named provider instance, and that
instance carries the transport-specific configuration.

## Shared API-provider fields

All API adapters may use:

- `adapter` — required adapter name
- `model` — provider-specific model identifier
- `base_url` — optional endpoint override for gateways / private deployments
- `api_version` — optional version pin for APIs that expose version headers

## Direct provider contracts

### `claude-api`

- Auth: `ANTHROPIC_API_KEY`
- Default endpoint: `https://api.anthropic.com/v1/messages`
- Model contract: Anthropic model name
- Notes:
  - direct vendor integration
  - currently text-only in this project

### `codex-api`

- Auth: `OPENAI_API_KEY`
- Default endpoint: `https://api.openai.com/v1/responses`
- Model contract: OpenAI Responses model name
- Notes:
  - `base_url` allows OpenAI-compatible gateway routing

### `gemini-api`

- Auth: `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- Default endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Model contract: Gemini model name

## Aggregator contracts

### `litellm-api`

- Auth: optional `LITELLM_API_KEY`, falls back to `OPENAI_API_KEY` if present
- Default endpoint: `http://localhost:4000`
- Model contract: routed provider model id (for example `openai/gpt-4.1-mini`)
- Required instance fields:
  - `model`
- Optional instance fields:
  - `base_url`
- Structured output:
  - supports project-level `json_schema` normalization through the OpenAI-compatible Responses contract
- Tools:
  - intentionally disabled in the project's normalized contract for now

### `copilot-api`

This adapter is intentionally defined as a **GitHub Models aggregator contract**.
That means the implementation targets GitHub's model-inference platform, not an
undocumented private Copilot endpoint.

- Auth: `GITHUB_TOKEN` or `GH_TOKEN`
- Default endpoint: `https://models.github.ai`
- Default API version: `2026-03-10`
- Model contract: `{publisher}/{model}` such as `openai/gpt-4.1`
- Optional instance fields:
  - `organization` — for org-attributed requests
  - `api_version`
  - `base_url`
- Structured output:
  - supports project-level `json_schema` via `response_format`
- Tools:
  - intentionally disabled in the project's normalized contract for now
- Why:
  - GitHub officially documents the inference API
  - it acts as a model aggregator across vendors

### `bedrock-api`

This adapter is defined around **Amazon Bedrock Converse**, not model-specific
Invoke payloads.

- Auth: standard AWS credential chain
- Runtime dependency: `boto3`
- API contract: Bedrock `Converse`
- Model contract: Bedrock `modelId`
- Required instance fields:
  - `model`
  - `region`
- Optional instance fields:
  - `aws_profile`
- Structured output:
  - not enabled in the project's normalized contract yet
- Tools:
  - intentionally disabled in the project's normalized contract for now
- Why Converse:
  - AWS documents Converse as the unified cross-model interface
  - it avoids leaking provider-specific JSON bodies into project config

## Capability policy

Current capability policy for aggregator adapters:

- `copilot-api`
  - `transport=api`
  - `provider_kind=aggregator`
  - `supports_json_schema=true`
  - `supports_tools=false` in the project for now

- `litellm-api`
  - `transport=api`
  - `provider_kind=aggregator`
  - `supports_json_schema=true`
  - `supports_tools=false` in the project for now

- `bedrock-api`
  - `transport=api`
  - `provider_kind=aggregator`
  - `supports_json_schema=false`
  - `supports_tools=false` in the project for now

The "false" values above are about THIS PROJECT'S normalized contract, not the
upstream platform's full surface area.

## Additional capability flags

The backend capability model now also exposes:

- `supports_system_prompt`
- `supports_streaming`
- `supports_response_format`
- `supports_org_routing`

These are currently conservative and mostly `false`, because the project still
normalizes around a simpler cross-provider execution contract. That is
intentional: capability metadata should describe what the project can use
reliably, not every upstream feature a vendor might support.

Current practical meanings:

- `supports_response_format`
  - the backend has a stable structured-output surface beyond plain text
  - currently true for `codex-api`, `litellm-api`, and `copilot-api`

- `supports_org_routing`
  - the backend exposes first-class organization/account routing in its request contract
  - currently true for `copilot-api`

## Error normalization contract

API adapters now normalize transport and provider failures into
`AgentResponse(raw={"error": ...})`.

Current normalized categories include:

- `auth`
- `permission`
- `not_found`
- `bad_request`
- `quota`
- `rate_limit`
- `timeout`
- `transport`
- `malformed_response`
- `server_error`
- `unknown`

The shared API transport maps network and HTTP failures first, then adapter
parsers refine provider-specific fields such as vendor error codes and statuses.
For example:

- Anthropic `rate_limit_error` -> `rate_limit`
- OpenAI-style `insufficient_quota` -> `quota`
- Gemini `UNAVAILABLE` -> `server_error`
- Bedrock `ThrottlingException` -> `rate_limit`

## Example

```yaml
research:
  execution:
    providers:
      primary_direct:
        adapter: claude-api
        model: claude-sonnet-4-5

      github_models:
        adapter: copilot-api
        model: openai/gpt-4.1
        organization: acme
        api_version: 2026-03-10

      aws_foundation:
        adapter: bedrock-api
        model: anthropic.claude-3-5-sonnet-20240620-v1:0
        region: us-east-1
        aws_profile: sandbox

      gateway_fast:
        adapter: litellm-api
        model: openai/gpt-4.1-mini
        base_url: http://localhost:4000
```

## Sources

- AWS Bedrock Converse: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
- AWS Bedrock inference API guide: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-api.html
- AWS Bedrock endpoints: https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html
- GitHub Models inference API: https://docs.github.com/en/rest/models/inference
