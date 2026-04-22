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
- `docs/design/streaming-contract.md` — proposed normalized streaming rollout
- `docs/design/api-tool-calling-contract.md` — proposed phased tool-calling contract
