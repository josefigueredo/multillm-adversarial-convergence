# MANIFEST

Purpose: quick inventory of the repository so a reader can understand where the main runtime, docs, configs, inputs, outputs, and tests live.

## Top-level map

- `README.md` — primary usage and architecture overview
- `MANIFEST.md` — this file; repository inventory
- `pyproject.toml` — Python project metadata and dependencies
- `uv.lock` — locked dependency graph for `uv`

## Source code

- `src/cli.py` — CLI entrypoint (`run`, `refine`, `plan`)
- `src/orchestrator.py` — `run` orchestration lifecycle and synthesis/finalization wiring
- `src/research_loop.py` — iterative research loop
- `src/evidence/` — references, provenance, and evidence artifact pipeline
- `src/deliverables/` — deliverable staging, citation verification, and export helpers
- `src/execution/` — execution plan, validation, diagnosis, repair, and integration
- `src/implement/` — implement/refine/plan loop orchestration and strategies
- `src/policy/` — HITL, trust, policy denial, runtime security, and sandbox execution
- `src/config.py` — YAML config schema and validation
- `src/strategy.py` — single / ensemble / adversarial / related runtime strategies
- `src/backends/` — backend adapters and registry
- `src/output_style.py` — run-mode output style profiles, conventions, and HTML theming
- `src/reporting.py` — HTML report rendering
- `src/artifacts.py` — artifact payload builders and report-writing helpers
- `src/audit_trail.py` — structured execution audit trail writer
- `src/portfolio.py` — cross-run portfolio aggregation
- `src/templates/` — HTML templates and CSS assets

## Prompts

- `prompts/` — prompt templates for research, synthesis, evaluation, refine, and plan flows

## Configurations

- `configs/_template.yaml` — annotated reference config
- `configs/smoke_test_*.yaml` — lightweight smoke configs
- `configs/localstack_alternatives_copilot_codex.yaml` — LocalStack alternatives raw/default run config
- `configs/localstack_alternatives_copilot_codex_paper.yaml` — synthesis-only paper-style variant
- `configs/localstack_alternatives_copilot_codex_technical.yaml` — synthesis-only technical-doc variant

## Inputs

- `input/` — copied source materials used by refine/plan examples and repo-local runs
- `input/iris/` — Iris PRD and plan inputs used for plan refinement

## Outputs

- `output/` — working run artifacts; ephemeral/generated runtime outputs
- `docs/showcase/` — persisted example outputs kept as documentation assets

### Showcase currently persisted

- `docs/showcase/localstack-alternatives/raw/` — default/raw rendering of the LocalStack alternatives run
- `docs/showcase/localstack-alternatives/paper/` — paper rendering of the same research corpus
- `docs/showcase/localstack-alternatives/technical/` — technical-doc rendering of the same research corpus
- `docs/showcase/localstack-alternatives/images/` — screenshots documenting the three render styles

## Documentation

- `docs/run.md` — run-mode guide
- `docs/refine.md` — refine-mode guide
- `docs/plan.md` — plan-mode guide
- `docs/design/` — design notes and architecture decisions
- `docs/archive/` — archived planning/history documents
- `docs/showcase/` — persisted showcase outputs and their documentation

## Benchmarks

- `benchmarks/` — reusable benchmark definitions and comparison inputs

## Tests

- `tests/` — automated test suite covering config, loops, artifacts, reporting, styles, and CLI behavior

## Operational conventions

- Run-mode output styles are configured in `reporting.output_style`
- `run.log` is the human-readable per-run log
- `audit_trail.jsonl` is the structured execution audit trail
- `docs/showcase/` is for durable example artifacts; `output/` is for live/generated run output

## Recommended reading order

1. `README.md`
2. `docs/run.md`
3. `MANIFEST.md`
4. `src/config.py`
5. `src/orchestrator.py`
6. `src/output_style.py`
