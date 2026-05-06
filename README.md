# Multi-LLM Adversarial Convergence Framework

Throw a topic at multiple LLMs. Let them argue, score each other, and iterate until the best version wins.

This framework adapts [Karpathy's autoresearch loop](https://github.com/karpathy/autoresearch) — same loop (hypothesise, execute, score, keep or discard, compress), but the substrate is knowledge, not weights. Multiple backends can argue with each other (adversarial), agree in parallel (ensemble), or take turns (serial).

## What it does

- **research** — `src.cli research` — autonomous iterative research on a topic. You get a scored, synthesised report with citations, certainty tables, and a full audit trail.
- **refine** — `src.cli refine` — converge a PRD, spec, or technical proposal. Multiple LLMs critique and rewrite until the document stabilises.
- **plan** — `src.cli plan` — converge an implementation plan. Same loop as refine, tuned for plan-shaped artifacts.

Two read-only helpers worth knowing: `src.cli explain` (inspect config or resume state without touching backends) and `src.cli doctor` (config health and output-run completeness checks).

## 30-second tour

```bash
uv sync

# Validate end-to-end without spending tokens
uv run python -m src.cli research --config configs/research/aws_api_gateway.yaml --dry-run

# Then run for real
uv run python -m src.cli research --config configs/research/aws_api_gateway.yaml
```

Same shape for `refine` and `plan` — point `--config` at a YAML, optionally append `--dry-run`.

To start your own, copy a template:

- Research → `configs/research/_template.yaml` (annotated)
- Refine → `configs/refine/prd_template.yaml`
- Plan → `configs/plan/plan_template.yaml`

The `configs/research/example_*.yaml` files show different backend setups — direct API, mixed CLI+API, LiteLLM aggregator, GitHub Models, Bedrock.

## Going deeper

| If you want | Read |
| --- | --- |
| The research-mode lifecycle, output styles, security model | [`docs/research.md`](docs/research.md) |
| How refine convergence works | [`docs/refine.md`](docs/refine.md) |
| How plan convergence works | [`docs/plan.md`](docs/plan.md) |
| To work on this codebase as an AI agent | [`AGENTS.md`](AGENTS.md) |
| Architecture rationale and contracts | [`docs/design/`](docs/design/) |

## What's actually in the box

- **Backends** — Claude, Codex, Gemini, Copilot. Each available as a CLI adapter or a direct API adapter. Aggregators too: LiteLLM, GitHub Copilot API, AWS Bedrock.
- **Output styles** for research synthesis: `default`, `paper`, `technical_doc`, `executive_brief`, `decision_memo`. Each can be refined further with `reporting.style_overrides` — see [output style](docs/research.md#output-style).
- **Security model** — declarative `security:` config section with optional sandbox enforcement, write-boundary control, network-access gating, and a per-tool capability registry. See [security policy](docs/research.md#security-policy).
- **Reproducibility** — every real run writes `run.log`, structured `audit_trail.jsonl`, an `effective_config.json` snapshot, and a runnable `rerun.sh` for exact replay.
- **Trust and certainty** — citations and claims carry a `trust_class`; first-pass certainty tables and PRISMA-style search/screening logs are emitted automatically.

## Requirements

- Python 3.10+
- At least one backend installed:
  - **CLIs**: [Claude Code](https://claude.ai/download) (recommended), [OpenAI Codex](https://developers.openai.com/codex), [Gemini CLI](https://github.com/google-gemini/gemini-cli), [GitHub Copilot CLI](https://docs.github.com/en/copilot)
  - **Direct APIs**: Anthropic, OpenAI, Google
  - **Aggregators**: LiteLLM, GitHub Copilot API, AWS Bedrock (`uv sync --extra bedrock`)

## Tests

```bash
uv sync --group dev
uv run pytest tests/ -v
```

## Design documents

- [`agentic-design-patterns.md`](docs/design/agentic-design-patterns.md) — 11 agentic patterns used, with architectural rationale and canonical references
- [`evaluation-architecture.md`](docs/design/evaluation-architecture.md) — evaluation pipeline rationale
- [`scientific-rigor-roadmap.md`](docs/design/scientific-rigor-roadmap.md) — PRISMA / GRADE roadmap
- [`api-provider-contracts.md`](docs/design/api-provider-contracts.md) — API adapter contracts
- [`streaming-contract.md`](docs/design/streaming-contract.md) — streaming contract and follow-up work
- [`api-tool-calling-contract.md`](docs/design/api-tool-calling-contract.md) — phased tool-calling contract
- [`raw-backend-output-policy.md`](docs/design/raw-backend-output-policy.md) — boundary for future raw payload capture
