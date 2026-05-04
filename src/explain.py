"""Human-readable config and run-state explainers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .output_style import build_output_style_presentation, summarize_output_style_overrides
from .run_paths import RunPaths
from .workflows.contracts import RESEARCH_CONTRACTS


def _workflow_contracts_lines(mode: str = "research") -> list[str]:
    """Return WORKFLOW CONTRACTS section lines for *explain config* output."""
    from .workflows.contracts import REFINE_CONTRACTS, PLAN_CONTRACTS

    _contracts_map = {
        "research": RESEARCH_CONTRACTS,
        "refine": REFINE_CONTRACTS,
        "plan": PLAN_CONTRACTS,
    }
    contracts = _contracts_map.get(mode, RESEARCH_CONTRACTS)

    lines: list[str] = [f"WORKFLOW CONTRACTS ({mode})"]
    for phase, contract in contracts.items():
        gate = "yes" if contract.human_gate else "no"
        lines.append(
            f"  {phase:<14} recovery: {contract.recovery_mode:<22}  human_gate: {gate}"
        )
    lines.append("")
    return lines


def explain_config_text(config: Any, *, config_path: Path | None = None) -> str:
    """Render a human-readable explanation of the effective research config.

    Does NOT create output directories, run backends, or instantiate any
    execution machinery.  Pure inspection of the resolved config object.
    """
    lines: list[str] = []

    if config_path is not None:
        lines.append(f"config: {config_path.resolve()}")

    # --- Research topic / goal -------------------------------------------------
    lines += [
        "",
        "RESEARCH",
        f"  topic:    {config.topic}",
        f"  goal:     {config.goal}",
    ]
    if config.dimensions:
        lines.append(f"  dimensions ({len(config.dimensions)}):")
        for dim in config.dimensions:
            lines.append(f"    - {dim}")
    else:
        lines.append("  dimensions: none configured")

    # --- Strategy / execution --------------------------------------------------
    lines += [
        "",
        "STRATEGY",
        f"  strategy:       {config.execution.strategy}",
        f"  max_iterations: {config.execution.max_iterations or 'unlimited'}",
        f"  stream:         {'enabled' if config.execution.stream else 'disabled'}",
    ]

    # --- Backend role mapping --------------------------------------------------
    backends = config.execution.backends
    lines += [
        "",
        "BACKEND ROLES",
        f"  primary:  {backends.primary}",
        f"  research: {', '.join(backends.research) if backends.research else '—'}",
        f"  judge:    {backends.judge_or_primary}",
        f"  utility:  {backends.utility_or_primary}",
    ]

    # --- Provider instances ----------------------------------------------------
    if config.providers:
        lines.append("")
        lines.append(f"PROVIDERS ({len(config.providers)})")
        for name, provider in config.providers.items():
            model_part = f" ({provider.model})" if getattr(provider, "model", None) else ""
            lines.append(f"  {name}: {provider.adapter}{model_part}")

    # --- Output style ----------------------------------------------------------
    style_label = build_output_style_presentation(config.reporting.output_style).get(
        "style_label", config.reporting.output_style
    )
    active_overrides = summarize_output_style_overrides(config.reporting.style_overrides)
    lines += [
        "",
        "OUTPUT STYLE",
        f"  style:     {config.reporting.output_style} ({style_label})",
        f"  overrides: {', '.join(active_overrides) if active_overrides else 'none'}",
    ]

    # --- Reporting outputs ----------------------------------------------------
    lines += [
        "",
        "REPORTING",
        f"  html: {'enabled' if config.reporting.export_html else 'disabled'}",
        f"  pdf:  {'enabled' if config.reporting.export_pdf else 'disabled'}",
    ]
    if config.reporting.report_title:
        lines.append(f"  title: {config.reporting.report_title}")

    # --- Security policy -------------------------------------------------------
    sec = config.security
    sb = sec.sandbox
    lines += [
        "",
        "SECURITY POLICY",
        f"  content_trust:       {sec.content_trust}",
        f"  tool_execution_mode: {sec.tool_execution_mode}",
        f"  allow_host_bash:     {sec.allow_host_bash}",
        f"  filesystem_writes_outside_output: {sec.allow_filesystem_write_outside_output}",
        f"  sandbox.mode:        {sb.mode}",
        f"  sandbox.scope:       {sb.scope}",
        f"  sandbox.filesystem:  {sb.filesystem_access}",
        f"  sandbox.network:     {sb.network_access}",
        f"  sandbox.backend:     {sb.backend}",
    ]
    if sb.backend == "container":
        lines += [
            f"  sandbox.container.image:     {sb.container.image}",
            f"  sandbox.container.workspace: {sb.container.container_workspace}",
        ]

    # --- HITL policy (MM08) ---------------------------------------------------
    from src.workflows.gates import GATES_BY_MODE

    hitl_mode = config.hitl.intervention_mode
    gate_count = len(GATES_BY_MODE.get(hitl_mode, frozenset()))
    lines += ["", "HITL POLICY", f"  intervention_mode: {hitl_mode}"]
    if gate_count == 0:
        lines.append("  active_gates:      none  (fully automated — no human gates)")
    else:
        lines.append(
            f"  active_gates:      {gate_count} gate(s) active"
            "  (run doctor config for gate details)"
        )

    # --- Artifact paths (dry-run preview) -------------------------------------
    stem = config_path.stem if config_path is not None else "run"
    output_dir = Path("output") / stem
    paths = RunPaths.for_output_dir(output_dir)
    lines += [
        "",
        "ARTIFACTS (default output paths)",
        f"  output_dir:       {output_dir}",
        f"  effective_config: {paths.effective_config}",
        f"  manifest:         {paths.manifest}",
        f"  report_html:      {paths.report_html}",
    ]

    # --- Workflow contracts ---------------------------------------------------
    lines.append("")
    lines.extend(_workflow_contracts_lines("research"))

    return "\n".join(lines)


def explain_resume_text(output_dir: Path) -> str:
    """Inspect an existing output directory and explain its resume state.

    Does NOT create directories, run backends, or instantiate any execution
    machinery.  Pure filesystem inspection of the saved run state.
    """
    if not output_dir.exists():
        return f"output directory not found: {output_dir}"

    paths = RunPaths.for_output_dir(output_dir)

    iter_files = (
        sorted(paths.iterations_dir.glob("iter_*.md"))
        if paths.iterations_dir.exists()
        else []
    )
    iteration_count = len(iter_files)

    artifact_checks = [
        ("iterations", paths.iterations_dir.exists() and iteration_count > 0),
        ("results.tsv", paths.results.exists()),
        ("knowledge_base.md", paths.knowledge_base.exists()),
        ("synthesis.md", paths.synthesis.exists()),
        ("report.html", paths.report_html.exists()),
        ("metrics.json", paths.metrics.exists()),
        ("effective_config.json", paths.effective_config.exists()),
        ("audit_trail.jsonl", paths.audit_trail.exists()),
    ]
    artifact_map = dict(artifact_checks)

    best_score: float | None = None
    run_status: str | None = None
    if paths.metrics.exists():
        try:
            data = json.loads(paths.metrics.read_text(encoding="utf-8"))
            best_score = data.get("best_score")
            run_status = data.get("run_status")
        except (json.JSONDecodeError, OSError):
            pass

    can_resume = iteration_count > 0
    is_complete = artifact_map["synthesis.md"] and artifact_map["report.html"]

    lines: list[str] = [f"output: {output_dir.resolve()}", ""]

    lines += ["RESUME STATUS", f"  resumable:        {'yes' if can_resume else 'no (no iteration files found)'}"]
    lines.append(f"  iterations_found: {iteration_count}")
    if best_score is not None:
        lines.append(f"  best_score:       {best_score}")
    if run_status:
        lines.append(f"  run_status:       {run_status}")
    if is_complete:
        lines.append("  note:             run appears complete (synthesis + report present)")

    lines += ["", "ARTIFACTS"]
    for name, present in artifact_checks:
        mark = "\u2713" if present else "\u2717"
        if name == "iterations":
            label = f"iterations ({iteration_count} files)" if present else "iterations (none found)"
        else:
            label = name
        lines.append(f"  {mark} {label}")

    reused: list[str] = []
    if iteration_count > 0:
        reused.append(f"{iteration_count} iteration file(s) (iter_*.md)")
    if artifact_map["results.tsv"]:
        reused.append("results.tsv (score history)")
    if artifact_map["knowledge_base.md"]:
        reused.append("knowledge_base.md (accumulated findings)")

    lines += ["", "ON RESUME — REUSED"]
    if reused:
        for item in reused:
            lines.append(f"  - {item}")
    else:
        lines.append("  (nothing — no resumable state found)")

    lines += [
        "",
        "ON RESUME — REGENERATED",
        "  - synthesis.md",
        "  - methods.md",
        "  - dashboard.json",
        "  - report.html",
        "  - report.pdf",
    ]

    return "\n".join(lines)


def explain_implement_config_text(config: Any, *, config_path: Path | None = None) -> str:
    """Render a human-readable explanation of an implement config.

    Does NOT create output directories, run backends, or instantiate any
    execution machinery.  Pure inspection of the resolved ImplementConfig object.
    """
    lines: list[str] = []

    if config_path is not None:
        lines.append(f"config: {config_path.resolve()}")

    target = config.target

    # ── Target repo contract ──────────────────────────────────────────────────
    lines += [
        "",
        "TARGET",
        f"  path:            {target.path.resolve()}",
        f"  execution_level: {target.execution_level}",
    ]
    if target.allowed_roots:
        lines.append(f"  allowed_roots:   {', '.join(str(r) for r in target.allowed_roots)}")
    else:
        lines.append("  allowed_roots:   (none — all target files reachable)")

    # ── Task / cycle config ───────────────────────────────────────────────────
    lines += [
        "",
        "TASK",
        f"  description:       {config.task_description or '(none)'}",
        f"  max_cycles:        {config.max_cycles}",
        f"  convergence_cycles:{config.convergence_cycles}",
    ]

    # ── Safety boundaries ─────────────────────────────────────────────────────
    lines += [
        "",
        "SAFETY BOUNDARIES",
        f"  allow_same_repo: {config.allow_same_repo}",
    ]
    if config.allow_same_repo:
        lines.append("  [!] self-hosting opt-in is active — target may be this planner repo")

    if target.allowed_roots:
        lines.append(
            f"  boundary enforcement: RESTRICTED to {', '.join(str(r) for r in target.allowed_roots)}"
        )
    else:
        lines.append("  boundary enforcement: PERMISSIVE (no allowed_roots declared)")

    lines.append("  violation outcome:    loop stops immediately, runner returns 1")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Publication pipeline explainer (MM11 Step 5)
# ---------------------------------------------------------------------------

_STAGE_ORDER = ("pending", "synthesize", "revise", "package", "export")

_NEXT_STAGE: dict[str, str] = {
    "pending": "synthesize",
    "synthesize": "revise",
    "revise": "package",
    "package": "export",
    "export": "complete",
}


def explain_domain_packages() -> str:
    """Return a human-readable summary of the Research OS bounded-context packages.

    Reports which domain package seams are active (introduced by MM12) and which
    were already packaged before MM12.  Flat-module imports remain backward-
    compatible throughout the migration; this function documents the canonical
    package boundaries operators and contributors should prefer going forward.

    Pure inspection — no side effects.
    """
    lines: list[str] = [
        "RESEARCH OS — DOMAIN PACKAGES",
        "═" * 40,
        "",
        "Package seams introduced by MM12:",
        "",
        "  src.evidence       Citations, provenance, references, reproducibility",
        "  src.deliverables   Publication pipeline, class configs, citation/export verification",
        "  src.execution      Execution plans, validation, diagnosis, repair loops",
        "  src.implement      Implement / plan / document loops, strategies, refiners",
        "  src.policy         HITL, trust, policy denial, security runtime, tool capabilities, sandbox",
        "",
        "Pre-existing package seams (unchanged by MM12):",
        "",
        "  src.workflows      Workflow state machine — states, transitions, gates, review packets",
        "  src.backends       LLM backend adapters",
        "  src.sandbox        Sandbox execution backends",
        "",
        "Domain migration complete (MM15): canonical package paths are the only",
        "supported public API.  Flat-module shims (e.g. src.hitl) were removed.",
    ]
    return "\n".join(lines)


def explain_pipeline_text(pipeline: "Any") -> str:  # DeliverablePipeline
    """Return a human-readable explanation of *pipeline*'s current publication state.

    Describes:
    - Topic and deliverable class identity
    - Completed stage and what comes next
    - Per-stage artifact summaries for completed stages

    Pure inspection — no side effects.
    """
    from .deliverables.pipeline import PipelineStage

    lines: list[str] = []

    class_label = pipeline.deliverable_class if pipeline.deliverable_class else "unclassed"
    lines += [
        f"topic:             {pipeline.topic}",
        f"deliverable_class: {class_label}",
    ]

    completed = pipeline.completed_stage.value
    next_stage = _NEXT_STAGE.get(completed, "complete")

    lines += [
        "",
        "PUBLICATION PIPELINE",
        f"  completed stage: {completed}",
        f"  next stage:      {next_stage}",
    ]

    lines.append("")
    lines.append("STAGES")

    stage_reached = _STAGE_ORDER.index(completed)

    for i, stage in enumerate(_STAGE_ORDER[1:], start=1):  # skip "pending"
        done = i <= stage_reached
        mark = "✓" if done else "✗"
        detail = ""

        if done:
            if stage == "synthesize" and pipeline.synthesis is not None:
                s = pipeline.synthesis
                wc = len(s.body.split())
                detail = f"{wc} words, {s.source_count} source(s), {len(s.key_findings)} finding(s)"
            elif stage == "revise" and pipeline.revision is not None:
                n = len(pipeline.revision.revision_notes)
                detail = f"{n} revision note(s)"
            elif stage == "package" and pipeline.package is not None:
                detail = f"format: {pipeline.package.format}"
            elif stage == "export" and pipeline.export is not None:
                exp = pipeline.export
                paths_str = ", ".join(exp.output_paths) if exp.output_paths else "(none)"
                detail = f"{len(exp.output_paths)} file(s): {paths_str} — exported_at: {exp.exported_at}"

        suffix = f" — {detail}" if detail else ""
        lines.append(f"  {mark} {stage}{suffix}")

    return "\n".join(lines)
