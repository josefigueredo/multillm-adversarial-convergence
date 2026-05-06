# AGENTS

Operating guide for AI coding agents working in this repository. Read this before making changes.

## Commands

```bash
# Install / sync deps
uv sync
uv sync --group dev          # include test deps
uv sync --extra bedrock      # include AWS Bedrock support

# Run modes (append --dry-run for validation only — no execution, no artifacts)
uv run python -m src.cli research    --config configs/research/<topic>.yaml
uv run python -m src.cli refine --config configs/refine/<doc>.yaml
uv run python -m src.cli plan   --config configs/plan/<plan>.yaml

# Inspection (no backends, no dirs created)
uv run python -m src.cli explain config --config <path>
uv run python -m src.cli explain resume --output <run_dir>

# Diagnostic (config health, output completeness)
uv run python -m src.cli doctor config --config <path>
uv run python -m src.cli doctor output --output <run_dir>

# Tests
uv run pytest tests/ -v
```

## Conventions

- Three modes — **research**, **refine**, **plan** — share execution semantics but each owns its config schema and convergence loop. Each is a CLI subcommand of the same name (`src.cli research|refine|plan`).
- Configs live in `configs/<mode>/`. Templates: `configs/research/_template.yaml`, `configs/refine/prd_template.yaml`, `configs/plan/plan_template.yaml`.
- YAML root key per mode: research-mode → `research:`, refine-mode → `document:` (note: not `refine:`), plan-mode → `plan:`.
- Run output layout (under `output/<run>/`): `run.log` (human), `audit_trail.jsonl` (structured append-only), `effective_config.json` (resolved snapshot), `tool_trace.json`, plus per-run mode-specific artifacts.
- Workspace boundary: `output/<run>/.workspace/` — owned by the run-scoped sandbox executor when `tool_execution_mode: sandboxed`.
- Backend identifiers are transport-aware: `claude-cli`, `codex-cli`, `gemini-cli`, `copilot-cli` (CLI adapters); `claude-api`, `codex-api`, `gemini-api`, `litellm-api`, `copilot-api`, `bedrock-api` (API adapters).
- Aggregator API adapters (`litellm-api`, `copilot-api`, `bedrock-api`) require explicit `execution.model` — no sensible default exists.
- Research output style profiles: `default`, `paper`, `technical_doc`, `executive_brief`, `decision_memo`; refined by `reporting.style_overrides`.

## DO

- Run `uv run pytest tests/ -v` after changes that touch config, orchestrator, backend, strategy, or sandbox code.
- Use `--dry-run` to validate config + provider wiring before triggering real runs.
- Inspect `audit_trail.jsonl` after sandbox/security work — every denial, write intent, and policy event lands there.
- Add new configs under the matching mode subfolder (`configs/research|refine|plan/`).
- For schema or backend changes, update both the live template config and any tests that load specific configs (`tests/test_config.py` is the main loader).
- Use `git mv` when relocating configs so rename history is preserved.

## DON'T

- **Don't build after changes** — repository rule. Verification is via tests, not build.
- **Don't add `.yaml` files to `configs/` root** — they belong in a mode subfolder.
- **Don't reference `configs/<file>.yaml` in docs** — always `configs/<mode>/<file>.yaml`. The mode subfolder is part of the canonical path.
- **Don't add `Co-Authored-By` or AI attribution to commits** — conventional commits only.
- **Don't widen sandbox policy** without confirming the change passes both `doctor config` and the sandbox enforcement tests.
- **Don't bypass `--no-verify`, `--no-gpg-sign`, or hook-skipping flags** without explicit user authorization.

## Repository inventory

### Source

- `src/cli.py` — CLI entrypoint (`research`, `refine`, `plan`, `explain`, `doctor`)
- `src/orchestrator.py` — research orchestration lifecycle and synthesis/finalization
- `src/research_loop.py` — iterative research loop
- `src/config.py` — YAML config schemas and validation (Research / Document / Plan)
- `src/strategy.py` — single / ensemble / adversarial / parallel / serial / specialist strategies
- `src/backends/` — backend adapters (CLI, API, aggregator) and registry
- `src/evidence/` — references, provenance, and evidence artifact pipeline
- `src/deliverables/` — deliverable staging, citation verification, export helpers
- `src/execution/` — execution plan, validation, diagnosis, repair, integration
- `src/implement/` — refine/plan loop orchestration and strategies
- `src/policy/` — HITL, trust, policy denial, runtime security, sandbox executor
- `src/output_style.py` — research output style profiles, conventions, HTML theming
- `src/reporting.py` — HTML report rendering
- `src/artifacts.py` — artifact payload builders and report-writing helpers
- `src/audit_trail.py` — structured execution audit trail writer
- `src/portfolio.py` — cross-run portfolio aggregation
- `src/templates/` — HTML templates and CSS

### Configs

- `configs/research/` — research-mode configs; `_template.yaml` is the annotated reference
- `configs/refine/` — refine-mode (document convergence) configs; `prd_template.yaml` is the reference
- `configs/plan/` — plan-mode configs; `plan_template.yaml` is the reference

### Prompts

- `prompts/` — prompt templates for research, synthesis, evaluation, refine, and plan flows

### Inputs / outputs

- `input/` — operator-provided source materials (e.g., `input/iris/` for plan refinement)
- `output/` — live run artifacts (ephemeral, generated)
- `docs/showcase/` — durable example outputs persisted as documentation

### Documentation

- `README.md` — project overview, runtime rules, design doc index
- `docs/research.md` — research-mode reference
- `docs/refine.md` — refine-mode reference
- `docs/plan.md` — plan-mode reference
- `docs/design/` — architecture and contract design notes
- `docs/showcase/` — persisted showcase outputs

### Tests

- `tests/` — config, loop, artifact, reporting, style, CLI, sandbox enforcement

### Benchmarks

- `benchmarks/` — reusable benchmark definitions and comparison inputs

## Recommended reading order for a new agent

1. `README.md`
2. `docs/research.md` (lifecycle, output style, security policy)
3. `src/config.py` (schema authority)
4. `src/orchestrator.py` (research lifecycle wiring)
5. `src/output_style.py` (synthesis profile contract)
