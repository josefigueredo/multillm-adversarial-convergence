# Multi LLM Adversarial Convergence Framework

Multi-LLM autonomous research and document convergence framework.
Adapts [Karpathy's autoresearch pattern](https://github.com/karpathy/autoresearch) — replacing GPU training runs with LLM agent calls for deep, iterative research and document convergence on any topic.

Supports **Claude**, **Codex**, **Gemini**, and **Copilot** backends.

## Modes

| Mode | Command | Use it for |
|------|---------|------------|
| [**run**](docs/run.md) | `src.cli run` | Autonomous iterative research on any topic |
| [**refine**](docs/refine.md) | `src.cli refine` | Converge a PRD, spec, or technical proposal |
| [**plan**](docs/plan.md) | `src.cli plan` | Converge an implementation plan |

## Quick Start

```bash
uv sync
uv run python -m src.cli run --config configs/aws_api_gateway.yaml

# Validate config, backend wiring, and planned output paths without running research
uv run python -m src.cli run --config configs/aws_api_gateway.yaml --dry-run

# Validate refine / plan configs without executing convergence loops
uv run python -m src.cli refine --config configs/prd_template.yaml --dry-run
uv run python -m src.cli plan --config configs/plan_template.yaml --dry-run
```

Dry-run smoke commands are a good first check before a real run:

```bash
uv run python -m src.cli run --config configs/example_github_models.yaml --dry-run
uv run python -m src.cli refine --config configs/prd_template.yaml --dry-run
uv run python -m src.cli plan --config configs/plan_template.yaml --dry-run
```

Copy `configs/_template.yaml` for research, `configs/prd_template.yaml` for document refinement, or `configs/plan_template.yaml` for plan refinement.
Example starting points:
- `configs/example_direct_api.yaml`
- `configs/example_mixed_cli_api.yaml`
- `configs/example_litellm_only.yaml`
- `configs/example_github_models.yaml`
- `configs/example_bedrock.yaml`

Important runtime rules:
- aggregator adapters (`litellm-api`, `copilot-api`, `bedrock-api`) require explicit model identifiers
- `execution.system_prompt` is supported on the current API adapters and stripped automatically where unsupported
- `execution.stream` currently enables live research-phase progress in `run` for `claude-api`, `codex-api`, `gemini-api`, `litellm-api`, `copilot-api`, and `bedrock-api`
- `execution.retry_api_errors` retries retryable non-streaming API failures with exponential backoff; streaming calls and function-tool loops are intentionally excluded
- `run --dry-run` validates config loading, strategy/backend resolution, provider wiring, backend availability, and planned artifact paths without executing the research loop or writing run artifacts
- `refine --dry-run` and `plan --dry-run` validate config loading, backend/provider wiring, and planned artifact paths without executing convergence loops or writing run artifacts
- retry activity is now surfaced into machine-readable artifacts and HTML reports so runs can show when API retries happened by backend
- retry summaries now include dominant retry categories and the most unstable backend for a run
- normalized API function-tool calling is currently implemented for `claude-api`, `codex-api`, `gemini-api`, `litellm-api`, `copilot-api`, and `bedrock-api`, and only for non-streaming explicit tool-registered calls
- PRISMA-like `search_log.json` and `screening_log.json` artifacts now capture what sources were considered and which ones were included/excluded
- methodology now supports richer protocol fields such as `review_type`, `search_sources`, `stopping_criteria`, and scoring/stopping rationale
- reproducibility artifacts now include `prompt_snapshot.json` and a runnable `rerun.sh` script
- first-pass certainty tables are now written to `certainty_tables.json` and summarized in run dashboards/reports
- portfolio views now aggregate certainty rollups, including total and high-certainty conclusions across runs
- portfolio views now include certainty deltas versus the best certainty run and separate high-certainty recommendation counts
- HTML and PDF reports now include factor-level certainty detail for the current run
- tool-loop observability is now captured in run metrics/dashboard artifacts when normalized API function tools are used, including per-backend and per-tool counts
- per-run tool trace artifacts are now written to `tool_trace.json`, with redacted argument summaries and truncated output previews
- dashboard/report views now surface compact tool-trace failure highlights without exposing raw payloads
- portfolio views now aggregate retries and tool activity across runs so cross-run instability is visible
- HTML/PDF reports now surface tool-usage highlights when tool loops are used in a run
- API failures are normalized into stable categories such as `rate_limit`, `timeout`, `transport`, `quota`, and `server_error`

## Requirements

- Python 3.10+
- At least one backend configured:
  - CLI adapters:
  - [Claude Code](https://claude.ai/download) (`claude-cli`) — recommended
  - [OpenAI Codex](https://developers.openai.com/codex) (`codex-cli`)
  - [Google Gemini CLI](https://github.com/google-gemini/gemini-cli) (`gemini-cli`)
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) (`copilot-cli`)
  - Direct API adapters:
    - `claude-api`
    - `codex-api`
    - `gemini-api`
  - Aggregator API adapters:
    - `litellm-api`
    - `copilot-api`
    - `bedrock-api`

### Optional provider extras

- Bedrock support: `uv sync --extra bedrock`

## Tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

## Design Documents

- `docs/design/evaluation-architecture.md` — evaluation pipeline rationale, module boundaries, data flow
- `docs/design/scientific-rigor-roadmap.md` — PRISMA/GRADE-informed roadmap toward scientific rigor
- `docs/design/api-provider-contracts.md` — API adapter contracts for direct and aggregator providers
- `docs/design/streaming-contract.md` — current streaming contract and deferred follow-up work
- `docs/design/api-tool-calling-contract.md` — proposed phased tool-calling contract
- `docs/design/raw-backend-output-policy.md` — policy boundary for any future raw backend payload capture

Raw backend output capture remains **default-off**. The config now reserves:
- `reporting.capture_raw_backend_outputs`
- `reporting.raw_backend_output_max_chars`
- `reporting.raw_backend_output_redact`

Those fields define the future boundary, but raw payload persistence is still not implemented.
