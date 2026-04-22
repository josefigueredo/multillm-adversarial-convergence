# Backend Architecture Plan

This document turns the backend review into:

1. a **formal implementation roadmap**
2. a **backend architecture plan**
3. a **step-by-step refactor sequence**

It also embeds a **TDD strategy** wherever the current project structure allows safe incremental change.

---

## 1) Formal Implementation Roadmap

## Objective

Evolve the current backend layer from a **CLI-only adapter model** into a **provider platform** that supports:

- existing CLI adapters
- direct API adapters
- aggregator/gateway adapters

without breaking the current working project behavior.

### Target provider families

#### Direct providers

- `claude-cli`
- `claude-api`
- `codex-cli`
- `codex-api`
- `gemini-cli`
- `gemini-api`
- `copilot-cli`

#### Aggregator/gateway providers

- `copilot-api` *(treat as aggregator/gateway if implemented)*
- `bedrock-api`
- `litellm-api`

---

## Guiding principles

1. **Preserve current behavior first**
   - Existing CLI-driven workflows must keep working during the migration.

2. **Provider-first, not CLI-first**
   - “Backend” becomes a provider adapter abstraction.
   - CLI is one transport, not the architecture.

3. **Capabilities must drive behavior**
   - The orchestrator should validate and adapt behavior based on declared capabilities.

4. **Configuration must be uniform across modes**
   - `run`, `refine`, and `plan` should all build invocation options through the same path.

5. **TDD where possible**
   - Add/adjust tests before refactors when the existing code is already stable enough to lock behavior.

---

## Milestones

## Milestone A — Stabilize the current backend contract

### Goals

- unify execution option handling across `run`, `refine`, and `plan`
- validate configured backend/provider names consistently
- centralize option construction

### Deliverables

- shared execution option builder
- consistent config validation across all modes
- preserved behavior for all current CLI adapters

### TDD

- add tests first for:
  - `DocumentRefiner` using configured execution values instead of hardcoded `CallOptions(max_turns=10)`
  - `PlanRefiner` and `AutoResearcher` using the same option-building semantics
  - invalid backend names failing consistently in `ResearchConfig`, `DocumentConfig`, and `PlanConfig`

### Exit criteria

- all current backend tests pass
- new config validation tests pass
- no mode hardcodes backend invocation values outside the shared path

---

## Milestone B — Reframe the abstraction from CLI backend to provider adapter

### Goals

- rename the conceptual model from “CLI backend” to “provider adapter”
- add transport metadata
- separate direct vendors from aggregators

### Deliverables

- updated base abstractions
- transport-aware capabilities
- provider metadata model

### TDD

- add tests first for:
  - provider registration preserving backward compatibility
  - capability flags for CLI vs API providers
  - default-model translation behavior remaining stable

### Exit criteria

- current CLI providers still instantiate and run through the same registry/factory path
- the system can distinguish provider identity from transport identity

---

## Milestone C — Support configured provider instances

### Goals

- stop using only raw backend names for workflow roles
- allow named configured instances

### Example target

```yaml
providers:
  claude_main:
    adapter: claude-api
    model: claude-sonnet-4.6

  litellm_fast:
    adapter: litellm-api
    model: openai/gpt-4.1-mini
    base_url: http://localhost:4000

backends:
  primary: claude_main
  research: [litellm_fast]
  judge: claude_main
  utility: litellm_fast
```

### Deliverables

- provider instance config model
- role resolution against configured instances
- backward-compatible mapping from old names (`claude-cli`, `codex-cli`, etc.)

### TDD

- add tests first for:
  - instance-name resolution
  - same adapter with different models/endpoints
  - backward compatibility from legacy backend names

### Exit criteria

- roles reference configured instances cleanly
- legacy configs still work with warnings or internal normalization

---

## Milestone D — Add API transports and first API providers

### Goals

- implement the first direct API adapters
- establish one stable API transport foundation before adding aggregators

### Recommended initial providers

- `claude-api`
- `codex-api`
- `gemini-api`

### Deliverables

- API base adapter
- API invocation contract
- error normalization and response parsing conventions

### TDD

- test-first for:
  - request building
  - response normalization into `AgentResponse`
  - capability enforcement
  - timeout/error mapping

### Exit criteria

- API adapters can be selected in config and normalized into the shared invocation path

---

## Milestone E — Add aggregator/gateway providers

### Goals

- support providers that route to other models or vendor APIs

### Recommended order

1. `litellm-api`
2. `bedrock-api`
3. `copilot-api` *(only if the real access model is well understood)*

### Deliverables

- aggregator-specific config fields
- capability declarations aligned with real behavior
- documentation of differences from direct providers

### TDD

- test-first for:
  - model routing config
  - base URL / endpoint injection
  - provider capability differences
  - failure modes specific to aggregators

### Exit criteria

- aggregators work through the same provider instance model
- invalid capability assumptions fail fast

---

## Milestone F — Documentation and migration completion

### Goals

- document the new architecture clearly
- complete the migration path

### Deliverables

- updated `README.md`
- updated mode docs
- updated `MANIFEST.md`
- completed deprecation notes for legacy backend names

### Exit criteria

- a new contributor can understand:
  - provider vs transport
  - direct vs aggregator
  - instance-based configuration
  - how TDD protects refactors

---

## 2) Backend Architecture Plan

## Current state

The current system already has a solid base:

- shared `Backend` abstraction
- shared `CallOptions`
- shared `AgentResponse`
- registry-based backend discovery
- capability metadata

But it is still semantically centered on **CLI subprocess invocation**.

### Current strengths

- clean backend subclass contract
- auto-registration
- per-provider command/response adapters
- research-mode execution path is relatively mature

### Current weaknesses

- `run`, `refine`, and `plan` do not configure backends consistently
- document mode hardcodes invocation options too aggressively
- plan mode only exposes part of the execution surface
- config shape does not scale cleanly to multiple configured instances
- backend naming mixes provider identity with transport assumptions

---

## Target architecture

## A. Core concepts

### Provider Adapter

Represents “how the system talks to a model provider”.

Examples:

- `claude-cli`
- `claude-api`
- `litellm-api`

### Transport

Defines how invocation happens:

- `cli`
- `api`

### Provider Kind

Defines what kind of provider it is:

- `direct`
- `aggregator`

### Provider Instance

A configured, named use of an adapter.

Examples:

- `claude_main`
- `claude_budget`
- `litellm_fast`
- `bedrock_secure`

Workflow roles should point to **instances**, not raw adapters.

---

## B. Proposed model layers

### Layer 1 — Generic provider contract

Files to evolve:

- `src/backends/base.py`
- `src/backends/types.py`
- `src/backends/registry.py`

Responsibilities:

- registration/discovery
- provider capability declaration
- normalized response contract
- transport-agnostic invocation shape

### Layer 2 — Transport-specific behavior

Suggested options:

#### Option 1 — split by base classes

- `src/backends/base.py`
- `src/backends/base_cli.py`
- `src/backends/base_api.py`

#### Option 2 — transport packages

- `src/backends/transports/cli.py`
- `src/backends/transports/api.py`

### Recommendation

Use **Option 1 first**. Less churn, easier migration.

---

## C. Proposed data contracts

## ProviderCapabilities

Expand current capabilities toward:

- `transport`
- `provider_kind`
- `supports_json_schema`
- `supports_budget_cap`
- `supports_rate_limit_detection`
- `supports_tools`
- `supports_streaming`
- `supports_system_prompt`
- `supports_temperature`
- `supports_reasoning_controls`
- `default_model`

## Invocation options

Do **not** let one giant option bag rot the system.

Recommended split:

- `BaseCallOptions`
- `CliCallOptions`
- `ApiCallOptions`

### BaseCallOptions

- `model`
- `json_schema`
- `allowed_tools`
- `max_turns`
- `timeout_seconds`
- `metadata`

### CliCallOptions

- `working_directory`
- `sanitize_environment`
- `max_budget_usd`

### ApiCallOptions

- `base_url`
- `headers`
- `api_version`
- `temperature`
- `top_p`
- `max_tokens`
- `system_prompt`

---

## D. Provider instance configuration model

Recommended future config direction:

```yaml
research:
  execution:
    strategy: adversarial

    providers:
      claude_main:
        adapter: claude-api
        model: claude-sonnet-4.6

      codex_research:
        adapter: codex-api
        model: gpt-5.4

      litellm_fast:
        adapter: litellm-api
        model: openai/gpt-4.1-mini
        base_url: http://localhost:4000

    backends:
      primary: claude_main
      research: [codex_research, litellm_fast]
      judge: claude_main
      utility: litellm_fast
```

### Why this model

Because one adapter may be instantiated multiple ways:

- different models
- different endpoints
- different rate/cost profiles
- different roles in the same workflow

That is impossible to express cleanly if roles only point to raw backend names.

---

## E. Compatibility strategy

### Backward compatibility rules

Legacy values like:

- `claude-cli`
- `codex-cli`
- `gemini-cli`
- `copilot-cli`

should normalize internally to:

- `claude-cli`
- `codex-cli`
- `gemini-cli`
- `copilot-cli`

### Migration phases

#### Phase 1

- support old names silently or with warnings

#### Phase 2

- document deprecated naming clearly

#### Phase 3

- remove legacy shorthand only after the new provider-instance model is stable

---

## F. Validation rules

Centralize validation so configuration errors fail early.

### Required rules

- provider/adapter names must exist
- roles must resolve to configured instances
- judge should differ from research providers where blind review matters
- unsupported features must fail early:
  - tools
  - schema output
  - budget cap
  - transport-specific fields

### Capability-driven examples

- CLI-only fields must not be accepted by API-only providers
- API-only options must not leak into CLI adapters
- aggregators must declare only the capabilities they actually guarantee

---

## G. TDD policy for this architecture

The project already has tests around:

- backend registry
- backend parsing/invocation behavior
- config loading

So use **test-first refactors** whenever behavior already exists and needs preservation.

### Use TDD directly for

- config parsing/validation changes
- registry/factory changes
- option normalization
- invocation contract refactors
- provider capability rules
- response normalization

### Use characterization tests first for

- current CLI command building behavior
- current parse behavior for each backend
- legacy name resolution

### Use integration-style mocks instead of live vendor calls

Since the project works now and we should avoid unstable external dependencies in unit tests:

- mock subprocesses for CLI adapters
- mock HTTP clients for API adapters
- never depend on real credentials in the core test suite

---

## 3) Step-by-Step Refactor Sequence

This sequence is optimized to keep the project working while changes land incrementally.

## Step 1 — Lock current behavior with characterization tests

### Add/expand tests

- `tests/test_backends/test_registry.py`
  - verify current adapters resolve
  - prepare for alias coverage later

- `tests/test_backends/test_{claude,codex,gemini,copilot}.py`
  - ensure command-building and response parsing are locked

- `tests/test_config.py`
  - add missing document/plan backend validation cases

### Goal

Freeze today’s behavior before changing abstractions.

---

## Step 2 — Introduce a shared execution option builder

### Refactor target

Centralize `CallOptions` creation for:

- `AutoResearcher`
- `DocumentRefiner`
- `PlanRefiner`

### TDD

Write tests first asserting:

- `refine` no longer hardcodes `max_turns=10`
- `plan` and `run` derive invocation options through the same shared path
- timeout/model/tool settings are forwarded consistently where supported

### Expected code areas

- `src/orchestrator.py`
- `src/document_refiner.py`
- `src/plan_refiner.py`
- new shared helper/module if needed

---

## Step 3 — Validate provider names consistently in all config loaders

### TDD

Add tests first for:

- invalid backend names in document config
- invalid backend names in plan config
- invalid role assignments across all modes

### Expected code areas

- `src/config.py`

---

## Step 4 — Rename the conceptual layer to provider adapters

### Refactor

- keep current classes working
- improve naming/comments/docs first
- only rename symbols if the change is worth the churn

### TDD

- registry tests must continue to pass
- public imports must remain backward-compatible unless deliberately deprecated

### Suggested approach

Do a **semantic refactor first**, not a giant rename storm.

---

## Step 5 — Add transport/provider-kind metadata

### TDD

Add tests first for capabilities such as:

- `claude-cli` => `transport=cli`, `provider_kind=direct`
- `litellm-api` => `transport=api`, `provider_kind=aggregator`

### Expected code areas

- `src/backends/types.py`
- concrete provider adapters

---

## Step 6 — Add adapter aliases for future naming

### Goal

Support both:

- legacy names (`claude-cli`)
- explicit transport names (`claude-cli`)

### TDD

Add tests first:

- `get_backend("claude-cli")`
- `get_backend("claude-cli")`
- both return the same implementation class during migration

### Expected code areas

- `src/backends/registry.py`
- `src/backends/__init__.py`

---

## Step 7 — Introduce configured provider instances

### TDD

Add tests first for config like:

- one adapter used twice with different settings
- workflow roles resolving to configured instance names
- fallback behavior for legacy flat configs

### Expected code areas

- `src/config.py`
- `src/strategy.py`
- `src/orchestrator.py`
- `src/document_strategy.py`
- `src/plan_strategy.py`

### Notes

This is the first structurally significant change. Do it only after Steps 1–6 are stable.

---

## Step 8 — Add API base adapter

### TDD

Create test-first abstractions for:

- request creation
- timeout handling
- normalized error mapping
- normalized `AgentResponse`

### Expected code areas

- new `src/backends/base_api.py` *(recommended)*
- `src/backends/types.py`

---

## Step 9 — Implement first direct API adapters

### Recommended order

1. `claude-api`
2. `codex-api`
3. `gemini-api`

### TDD

Per adapter, add tests first for:

- request translation from normalized options
- response mapping into `AgentResponse`
- capability declaration
- unsupported option behavior

---

## Step 10 — Implement aggregator adapters

### Recommended order

1. `litellm-api`
2. `bedrock-api`
3. `copilot-api` *(only after clarifying its real contract)*

### TDD

Add tests first for:

- endpoint/base URL config
- model routing fields
- declared capability limits
- failure/timeout normalization

---

## Step 11 — Move all workflows onto provider-instance resolution

### TDD

Add end-to-end config-resolution tests for:

- `run`
- `refine`
- `plan`

using mocked providers only.

### Goal

Prove all three modes can consume the same provider configuration model.

---

## Step 12 — Finalize docs and migration notices

### Update

- `README.md`
- `MANIFEST.md`
- `docs/run.md`
- `docs/refine.md`
- `docs/plan.md`
- `docs/design/...`

### TDD relevance

No TDD here; use documentation review and config examples validated by parser tests.

---

## Recommended implementation batches

To keep risk under control, batch the work like this:

### Batch 1 — correctness and consistency

- Steps 1–3

### Batch 2 — architecture foundation

- Steps 4–6

### Batch 3 — scalable configuration

- Step 7

### Batch 4 — API transport

- Steps 8–9

### Batch 5 — aggregators

- Step 10

### Batch 6 — rollout and docs

- Steps 11–12

---

## Risks and tradeoffs

## Risk 1 — giant refactor syndrome

If CLI, API, naming, config, and strategy wiring are all changed at once, the codebase will become unstable fast.

### Mitigation

- keep each milestone small
- use characterization tests before structural changes

## Risk 2 — fake symmetry between providers

Not all providers support the same options.

### Mitigation

- let capabilities drive validation
- document direct vs aggregator behavior explicitly

## Risk 3 — config migration confusion

Users may assume raw backend names still mean the same thing forever.

### Mitigation

- add aliases
- normalize internally
- emit clear deprecation messaging later

---

## Recommended first implementation task

If executing this plan now, start with:

1. add tests that expose current mode inconsistencies
2. centralize invocation option building
3. make `refine` and `plan` honor the same execution contract as `run` where appropriate

That gives immediate architectural value with the lowest migration risk.
