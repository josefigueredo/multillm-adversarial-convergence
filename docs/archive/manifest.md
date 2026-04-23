# MANIFEST

Quick project map for humans reviewing or extending this repository.

## What this repo is

`autoresearch` is a Python CLI framework for multi-LLM convergence workflows with three modes:

- `run` — autonomous research loops
- `refine` — document/PRD convergence
- `plan` — implementation-plan convergence

Primary entrypoint:

- `src/cli.py`

## Top-level layout

```text
.
├── README.md                 # high-level product overview and quick start
├── pyproject.toml            # package metadata + CLI entrypoint
├── configs/                  # example and template YAML configs for all modes
├── docs/                     # mode docs + design notes
├── prompts/                  # prompt templates used by agents/backends
├── src/                      # application code
├── tests/                    # pytest coverage across config, loops, backends, artifacts
├── input/                    # user/source material for runs (workspace data)
├── output/                   # generated run outputs (workspace data)
└── benchmarks/               # benchmark-related notes/assets
```

## Source map

### CLI and configuration

- `src/cli.py` — parses `run`, `refine`, and `plan` subcommands and boots the right orchestrator
- `src/config.py` — dataclass-based config loading/validation for research, document, and plan workflows

### Research mode (`run`)

- `src/orchestrator.py` — `AutoResearcher`, main research loop and artifact finalization
- `src/research_loop.py` — iteration loop helpers / flow control
- `src/strategy.py` — single/ensemble/adversarial/parallel/serial/specialist strategies
- `src/scorer.py` — heuristic + judge scoring support
- `src/constraints.py` — goal-shaping, lightweight-mode constraints, synthesis context helpers
- `src/run_state.py` — usage/cost/token accounting and resume state
- `src/run_io.py` — output directory/bootstrap helpers

### Document mode (`refine`)

- `src/document_refiner.py` — 3-phase document convergence orchestrator
- `src/document_loop.py` — per-cycle state and stop conditions
- `src/document_strategy.py` — builder/challenger/persona/verifier/arbitrator flow
- `src/hitl.py` — deferred human-input handling

### Plan mode (`plan`)

- `src/plan_refiner.py` — 3-phase plan convergence orchestrator
- `src/plan_loop.py` — per-cycle state and stop conditions
- `src/plan_strategy.py` — reviewer/persona/verifier/arbitrator plan flow

### Outputs, reporting, and evaluation

- `src/artifacts.py` — machine-readable payload builders (`run_manifest.json`, `metrics.json`, etc.)
- `src/provenance.py` — claims/citations/conflict extraction and evidence linking
- `src/comparison.py` — reference-run and benchmark comparison helpers
- `src/semantic_eval.py` — semantic review/calibration helpers
- `src/reporting.py` — HTML report rendering
- `src/pdf_report.py` — PDF rendering
- `src/portfolio.py` — cross-run portfolio/dashboard aggregation
- `src/templates/` — HTML/CSS partials for reports and portfolio

### Backend adapters

- `src/backends/base.py` — shared backend abstractions
- `src/backends/types.py` — response/call capability types
- `src/backends/registry.py` — backend lookup and registration
- `src/backends/claude.py`
- `src/backends/codex.py`
- `src/backends/gemini.py`
- `src/backends/copilot.py`
- `src/backends/jsonl.py` — structured logging/output helper backend support

## Prompt inventory

- `prompts/research.md`, `hypothesis.md`, `critique.md`, `evaluate.md`, `merge.md`, `synthesize.md`
- `prompts/prd_*.md` — document refinement prompts
- `prompts/plan_*.md` — plan refinement prompts
- `prompts/generate_readme.md`, `generate_docs_index.md` — phase-3 output indexing prompts

## Documentation map

- `docs/run.md` — research mode
- `docs/refine.md` — document refinement mode
- `docs/plan.md` — plan refinement mode
- `docs/design/evaluation-architecture.md` — evaluation/reporting architecture
- `docs/design/scientific-rigor-roadmap.md` — rigor roadmap and limitations

## Data directories

- `input/` — source material checked into the workspace for runs/refinement
- `output/` — generated artifacts from previous executions; useful as examples, not source code

## Review notes

- The repo already has strong mode-level documentation, but it did **not** have a root-level file that maps code modules to responsibilities.
- This `MANIFEST.md` exists to reduce onboarding cost when someone asks for a project review or needs to navigate the codebase quickly.
- Current user edits already existed in:
  - `.gitignore`
  - `configs/iris_poc_curriculum_plan.yaml`
  - `src/backends/claude.py`
  - `input/` (untracked)
  This manifest was added without modifying those files.
