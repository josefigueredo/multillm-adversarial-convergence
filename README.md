# Autoresearch

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

## Requirements

- Python 3.10+
- At least one AI coding CLI installed and authenticated:
  - [Claude Code](https://claude.ai/download) (`claude`) — recommended
  - [OpenAI Codex](https://developers.openai.com/codex) (`codex`)
  - [Google Gemini CLI](https://github.com/google-gemini/gemini-cli) (`gemini`)
  - [GitHub Copilot CLI](https://docs.github.com/en/copilot) (`copilot`)

## Tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

## Design Documents

- `docs/design/evaluation-architecture.md` — evaluation pipeline rationale, module boundaries, data flow
- `docs/design/scientific-rigor-roadmap.md` — PRISMA/GRADE-informed roadmap toward scientific rigor
