# Raw Backend Output Capture Policy

This document defines the policy boundary for storing raw backend outputs in
scientific-rigor and reproducibility artifacts.

## Current decision

Raw backend outputs are **not captured by default**.

Current reproducibility artifacts intentionally stop at:

- `run_manifest.json`
- `prompt_snapshot.json`
- `rerun.sh`

That boundary is deliberate.

## Why this needs policy first

Raw backend payloads can introduce real problems:

- secret leakage (tokens, headers, session identifiers, hidden tool arguments)
- artifact bloat from long provider payloads
- noisy diffs with little reproducibility value
- provider-specific junk that becomes expensive to keep forever
- accidental persistence of intermediate responses that are not authoritative

So before implementation, the project needs an explicit storage contract.

## Recommended policy

If raw backend capture is implemented later, it should be:

- **opt-in only**
- **final-response first**
- **redacted before write**
- **size-capped**

## Agreed config boundary

The config surface is now reserved as:

- `reporting.capture_raw_backend_outputs` (default `false`)
- `reporting.raw_backend_output_max_chars` (default `20000`)
- `reporting.raw_backend_output_redact` (default `true`)

These fields define the future implementation boundary, but they do **not**
mean raw payload capture is active yet.

## Scope recommendation

### In scope for a first implementation

- final backend response payloads
- final backend error payloads
- one file per run under a dedicated directory such as `raw_backend_outputs/`

### Out of scope for a first implementation

- every streamed chunk
- every intermediate tool-loop turn
- full provider request headers
- unbounded provider-native trace dumps

## Redaction requirements

Any implementation should redact at least:

- `authorization`
- `api_key`
- `token`
- `access_token`
- `refresh_token`
- `password`
- `secret`
- provider-specific session identifiers where feasible

## Size policy

Recommended first limits:

- cap each stored payload aggressively
- include:
  - original character count
  - truncated flag
  - backend name
  - model
  - timestamp

## Source-of-truth rule

Captured raw outputs are **audit artifacts**, not semantic source of truth.

The source-of-truth contract remains:

- final parsed `AgentResponse`
- final written artifacts (`synthesis.md`, provenance JSON, reports)

## Recommendation

Do not implement raw backend output capture until:

1. config shape is agreed
2. redaction rules are agreed
3. size limits are agreed
4. first-slice scope is limited to final responses/errors
