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
| **explain** | `src.cli explain` | Inspect config or resume state without executing |
| **doctor** | `src.cli doctor` | Diagnose config health and output-run completeness |

## Quick Start

```bash
uv sync
uv run python -m src.cli run --config configs/aws_api_gateway.yaml

# Validate config, backend wiring, and planned output paths without running research
uv run python -m src.cli run --config configs/aws_api_gateway.yaml --dry-run

# Validate refine / plan configs without executing convergence loops
uv run python -m src.cli refine --config configs/prd_template.yaml --dry-run
uv run python -m src.cli plan --config configs/plan_template.yaml --dry-run

# Inspect effective config before running (no backends, no dirs created)
uv run python -m src.cli explain config --config configs/aws_api_gateway.yaml

# Inspect a paused run's resume state (no backends, pure filesystem inspection)
uv run python -m src.cli explain resume --output output/aws_api_gateway
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
- `explain config --config <path>` prints a human-readable explanation of the effective config (topic, strategy, backend roles, providers, output style, security policy, artifact paths) without touching the network, creating dirs, or running backends
- `explain resume --output <dir>` inspects an existing run output directory and reports resume readiness (iteration count, artifact presence, best score, reuse vs regenerate breakdown) without executing anything
- `security:` is now a first-class config section; Milestone 1 policy fields: `content_trust` (`strict` | `permissive`), `tool_execution_mode` (`direct` | `sandboxed`), and a `sandbox:` sub-section (`mode`, `scope`, `filesystem_access`, `network_access`); see [Security policy](docs/run.md#security-policy)
- **Milestone 2 — runtime-enforced security:** `allow_host_bash: false` hard-blocks any backend call that includes `Bash` in `allowed_tools` (raises `PolicyDeniedError`, audit event emitted before exception); `sandbox.filesystem_access` controls the write boundary checked by `guard_path_write` (`output_only` → `output_dir`, `workspace_only` → `output_dir/.workspace/`); every real run creates `output_dir/.workspace/` as the run-scoped workspace boundary
- `policy_denied` events in `audit_trail.jsonl` record every enforcement denial with `reason_code`, `policy_field`, `requested_action`, and (when applicable) `requested_path` / `allowed_boundary` — denial events are always written before the exception propagates
- `sandbox_initialized` and `sandbox_policy_applied` events in `audit_trail.jsonl` record workspace creation and active runtime policy at setup time
- `effective_config.json` is written at run start as a full normalized snapshot of the resolved config (topic, dimensions, methodology, evaluation, scoring, execution, security, reporting, providers, backends) — useful for auditing exactly what a run executed with
- real runs now write a human-readable `run.log` plus a structured `audit_trail.jsonl` audit trail in the output directory
- `audit_trail.jsonl` records step start/completion/failure events, files created or updated by each step, and sandbox/security events
- `reporting.output_style` now lets `run` choose the synthesis prose/profile:
  - `default`
  - `paper`
  - `technical_doc`
  - `executive_brief`
  - `decision_memo`
- `reporting.style_overrides` now lets `run` refine that profile with optional controls like executive summary on/off, comparison table on/off, recommendation mode, and citation mode
- `reporting.style_overrides` now also supports methodology/limitations/next-actions toggles plus section ordering (`standard`, `recommendation_first`, `evidence_first`)
- HTML/PDF report presentation now follows the selected `run` output style with style-aware labels/titles (for example paper-style methodology labels or executive-brief framing)
- dry-run summaries plus machine-readable run artifacts now surface the selected style label and active override labels for easier operator verification
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
- **Milestone 3 — diagnostics, trust, and deterministic references:**
- `autoresearch doctor config --config <path>` validates a config file and prints a security enforcement truth table (enforced vs declared-only fields) plus operator risk notes; exit 0 (healthy) / 1 (warnings present); see [Doctor commands](docs/run.md#doctor-commands)
- `autoresearch doctor output --output <dir>` inspects a run output directory and reports run classification (complete / partial / empty), artifact status, resumability (what artifacts are actually reusable), and synthesis readiness; exit 0 (complete) / 1 (warnings/incomplete)
- every `citations.json` and `claims.json` record now carries a `trust_class` field; active classes: `untrusted_web_content` (URL citations), `user_provided_source_material` (local/operator-provided source files), `inferred_claim` (LLM-synthesized claims); `dashboard.json` includes a `trust_summary` count by class
- when `reporting.output_style: paper`, `synthesis.md` receives a deterministic `## References` section built from `citations.json`; URLs are deduplicated by normalized URL (tracking params stripped), numbered, and formatted as markdown links; non-paper styles are unaffected

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
