"""Doctor diagnostics — inspect config and run health without side effects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import ResearchConfig


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class DoctorReport:
    """Result of a doctor check."""

    text: str
    exit_code: int  # 0 = healthy, 1 = warnings / errors


# ---------------------------------------------------------------------------
# Security enforcement truth table (Milestone 4 ground-truth)
# ---------------------------------------------------------------------------

#: Fields that are *actively enforced* in runtime code (AutoResearcher).
_ENFORCED: dict[str, str] = {
    "allow_host_bash": "hard-blocks Bash tool in _call_with",
    "sandbox.filesystem_access": "write gate via guard_path_write + SandboxExecutor",
    "allow_filesystem_write_outside_output": "broadens write boundary in is_write_allowed",
}

#: Fields enforced at *dispatch level* when ``sandbox_active=True``.
#: Not OS/kernel-level — enforced at execution-dispatch time.
_DISPATCH_ENFORCED: dict[str, str] = {
    "tool_execution_mode: sandboxed": (
        "workspace cwd + write boundary + network gate at executor-dispatch level "
        "(not OS/kernel-level) when sandbox_active=True"
    ),
    "sandbox.network_access": (
        "WebSearch and WebFetch gated at dispatch level; "
        "not OS firewalling; requires sandbox_active=True"
    ),
}

#: Fields that are *declared in config* but not yet operationally enforced.
_DECLARED_ONLY: dict[str, str] = {
    "content_trust": "not yet evaluated at runtime",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_tools(allowed_tools: str) -> set[str]:
    return {t.strip() for t in allowed_tools.split(",") if t.strip()}


def _backend_validity_lines(config: "ResearchConfig") -> tuple[list[str], list[str]]:
    """Return (lines, warnings) for backend validity section."""
    from src.backends import valid_backends

    valid = set(valid_backends())
    all_names = config.execution.backends.all_backend_names()

    lines: list[str] = []
    warnings: list[str] = []
    for name in sorted(all_names):
        if name in valid:
            lines.append(f"  {name:<30} OK")
        else:
            lines.append(f"  {name:<30} [WARN] unknown backend")
            warnings.append(f"Unknown backend '{name}' — not in registry.")
    return lines, warnings


def _enforcement_table_lines(config: "ResearchConfig") -> list[str]:
    """Return the security enforcement truth table lines."""
    sec = config.security
    sb = sec.sandbox
    sandbox_active = sec.tool_execution_mode == "sandboxed" and sb.mode == "tool_calls"
    lines: list[str] = []

    lines.append("  Field                                   Status")
    lines.append("  " + "-" * 66)

    # Always-enforced fields
    bash_status = "ENFORCED" if not sec.allow_host_bash else "ENFORCED (allow_host_bash=true → Bash permitted)"
    lines.append(f"  {'allow_host_bash':<39} {bash_status}")
    lines.append(f"  {'sandbox.filesystem_access':<39} ENFORCED  (guard_path_write + executor)")
    lines.append(
        f"  {'allow_filesystem_write_outside_output':<39} "
        f"{'ENFORCED  (broadens write roots)' if sec.allow_filesystem_write_outside_output else 'ENFORCED  (default: output_only)'}"
    )

    # tool_execution_mode
    if sec.tool_execution_mode == "sandboxed":
        if sandbox_active:
            lines.append(
                f"  {'tool_execution_mode: sandboxed':<39} dispatch-enforced  (workspace cwd + executor routing)"
            )
        else:
            lines.append(
                f"  {'tool_execution_mode: sandboxed':<39} declared intent  (sandbox.mode≠tool_calls; not active)"
            )
    else:
        lines.append(
            f"  {'tool_execution_mode: direct':<39} direct  (no sandbox layer)"
        )

    # sandbox.network_access
    net_label = f"sandbox.network_access: {sb.network_access}"
    if sb.network_access == "unrestricted":
        lines.append(f"  {net_label:<39} unrestricted  (no gating)")
    elif sandbox_active:
        lines.append(f"  {net_label:<39} dispatch-enforced  (WebSearch/WebFetch; not OS-level)")
    else:
        lines.append(f"  {net_label:<39} declared intent  (no effect without sandbox_active)")

    lines.append(f"  {'content_trust':<39} declared-only  (not yet runtime-evaluated)")
    return lines


def _tool_coverage_lines(config: "ResearchConfig") -> tuple[list[str], list[str]]:
    """Return (lines, issues) for the sandbox tool coverage section.

    Surfaces (MM06 isolation maturity):
    - sandbox backend type (local-process / N/A) — 3-state
    - env shaping status (active vs inactive) — 3-state
    - env policy strategy summary (required/optional/denied/effective counts)
    - dispatch-level network enforcement scope
    - write-intent audit status (audit-only; not a deny gate)
    - unclassified tool policy (deny in sandbox, pass in direct)
    - capability coverage stats (classified/total fraction)
    - per-tool classification table with capability annotations

    Issues are emitted when ``sandbox_active=True`` and unclassified tools
    exist in ``allowed_tools`` — those tools will be denied at runtime.
    """
    from src.tool_capabilities import classify_tool, coverage_stats

    sec = config.security
    sandbox_active = sec.tool_execution_mode == "sandboxed" and sec.sandbox.mode == "tool_calls"
    sandbox_declared = sec.tool_execution_mode == "sandboxed"
    tools = sorted(_parse_tools(config.execution.allowed_tools))

    lines: list[str] = []
    issues: list[str] = []

    # Sandbox backend type — 3 states
    if sandbox_active:
        lines.append(
            "  sandbox backend:          local-process"
            "  (LocalProcessBackend — process-level isolation)"
        )
    elif sandbox_declared:
        lines.append(
            "  sandbox backend:          local-process"
            "  (LocalProcessBackend — declared, not active;"
            " set sandbox.mode: tool_calls to enable)"
        )
    else:
        lines.append(
            "  sandbox backend:          N/A  (direct mode — no sandbox substrate)"
        )

    # Env shaping status — three distinct states
    if sandbox_active:
        lines.append(
            "  env shaping:              ACTIVE"
            "  (build_environment filters to allowlist; process-level, not container-grade)"
        )
    elif sec.tool_execution_mode == "direct":
        lines.append(
            "  env shaping:              inactive  (direct mode — ambient env inherited)"
        )
    else:
        # sandboxed declared but sandbox.mode != tool_calls → not active
        lines.append(
            "  env shaping:              inactive  (sandbox declared but not active"
            " — ambient env inherited; set sandbox.mode: tool_calls to enable)"
        )

    # Env policy summary — only when sandbox substrate is declared
    if sandbox_declared:
        from src.sandbox.backends.local_process import SandboxEnvPolicy
        strat = SandboxEnvPolicy().strategy_summary()
        opt_label = "active" if strat["optional_active"] else "suppressed"
        if sandbox_active:
            lines.append(
                f"  env policy:               required={strat['required']},"
                f" optional={strat['optional']} ({opt_label}),"
                f" denied={strat['denied']} → effective={strat['effective']} vars"
            )
        else:
            lines.append(
                f"  env policy:               default local-process policy (not active —"
                f" required={strat['required']},"
                f" optional={strat['optional']},"
                f" denied={strat['denied']} → effective={strat['effective']})"
            )

    # Network enforcement scope
    lines.append(
        "  network enforcement:      dispatch-level"
        "  (WebSearch, WebFetch; not OS-level firewall)"
    )

    # Write-intent audit — only when sandbox substrate is declared
    if sandbox_active:
        lines.append(
            "  write-intent audit:       enabled"
            "  (may_write tools emit dispatch_write_intent to audit trail — not a deny gate)"
        )
    elif sandbox_declared:
        lines.append(
            "  write-intent audit:       inactive  (sandbox not active)"
        )
    # direct mode: no write-intent audit line

    # Unclassified tool policy — three distinct states
    if sandbox_active:
        lines.append(
            "  unclassified tool policy: denied (tool_unclassified) when sandbox_active=True"
        )
    elif sec.tool_execution_mode == "direct":
        lines.append(
            "  unclassified tool policy: allowed in direct mode"
            "  (sandbox mode would deny unclassified tools)"
        )
    else:
        lines.append(
            "  unclassified tool policy: allowed (sandbox not active"
            " — would be denied if sandbox enabled)"
        )

    # Capability coverage stats summary
    stats = coverage_stats(tools)
    unclassified_count = stats["unclassified"]
    if unclassified_count > 0:
        lines.append(
            f"  tool coverage:            {stats['classified']}/{stats['total']} classified"
            f"  ({unclassified_count} unclassified)"
        )
    else:
        lines.append(
            f"  tool coverage:            {stats['classified']}/{stats['total']} classified"
        )

    # Per-tool classification table
    lines.append("")
    lines.append("  Tool                    Classification")
    lines.append("  " + "-" * 52)

    unclassified: list[str] = []
    for name in tools:
        caps = classify_tool(name)
        if caps is None:
            lines.append(f"  {name:<24} UNCLASSIFIED")
            unclassified.append(name)
        else:
            cap_parts: list[str] = []
            if caps.uses_host_shell:
                cap_parts.append("host-shell")
            if caps.uses_network:
                cap_parts.append(f"network ({caps.destination_type or 'any'})")
            if caps.may_write:
                cap_parts.append("write")
            cap_str = ", ".join(cap_parts) if cap_parts else "none"
            lines.append(f"  {name:<24} classified  [{cap_str}]")

    # Emit issues for sandbox + unclassified tool combinations
    if sandbox_active:
        for name in unclassified:
            issues.append(
                f"'{name}' is unclassified and will be denied at dispatch"
                " when sandbox_active=True (tool_unclassified)."
            )

    return lines, issues


def _risk_note_lines(config: "ResearchConfig") -> tuple[list[str], list[str]]:
    """Return (note_lines, issues) for operator warnings.

    Every risk note is also added to *issues* so that it drives exit_code = 1.
    """
    from src.tool_capabilities import classify_allowed_tools

    sec = config.security
    tools = _parse_tools(config.execution.allowed_tools)
    sandbox_active = sec.tool_execution_mode == "sandboxed" and sec.sandbox.mode == "tool_calls"
    notes: list[str] = []
    issues: list[str] = []

    # Host-shell risk: use capability metadata, not hardcoded tool names.
    # Any tool classified with uses_host_shell=True triggers this warning.
    host_shell_tools = sorted(
        name for name, caps in classify_allowed_tools(list(tools))
        if caps and caps.uses_host_shell
    )
    if sec.allow_host_bash and host_shell_tools:
        tool_list = ", ".join(host_shell_tools)
        msg = (
            f"allow_host_bash is true AND host-shell tool(s) in allowed_tools"
            f" ({tool_list}) — host shell is exposed to the agent."
        )
        notes.append(f"  [!] {msg}")
        issues.append(msg)

    if sec.tool_execution_mode == "sandboxed" and not sandbox_active:
        msg = (
            "tool_execution_mode=sandboxed but sandbox.mode is not tool_calls"
            " — sandbox enforcement is not active."
            " Set sandbox.mode: tool_calls to enable executor-dispatch enforcement."
        )
        notes.append(f"  [!] {msg}")
        issues.append(msg)

    if sec.sandbox.network_access != "unrestricted" and not sandbox_active:
        msg = (
            f"sandbox.network_access={sec.sandbox.network_access} declared"
            " but has no operational effect — requires sandbox_active"
            " (tool_execution_mode=sandboxed AND sandbox.mode=tool_calls)."
        )
        notes.append(f"  [!] {msg}")
        issues.append(msg)

    return notes, issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def doctor_config_text(config: "ResearchConfig") -> DoctorReport:
    """Inspect *config* and return a DoctorReport (text + exit code).

    This is pure inspection — no I/O, no backends, no dirs created.

    Args:
        config: A fully-loaded ResearchConfig.

    Returns:
        DoctorReport with text and exit_code (0=healthy, 1=warnings).
    """
    issues: list[str] = []

    backend_lines, backend_warns = _backend_validity_lines(config)
    issues.extend(backend_warns)

    enforcement_lines = _enforcement_table_lines(config)
    coverage_lines, coverage_issues = _tool_coverage_lines(config)
    issues.extend(coverage_issues)
    risk_lines, risk_warns = _risk_note_lines(config)
    issues.extend(risk_warns)

    health = "OK" if not issues else f"WARNINGS ({len(issues)} issue{'s' if len(issues) != 1 else ''})"
    exit_code = 0 if not issues else 1

    parts: list[str] = []
    parts.append(f"HEALTH: {health}")
    parts.append("")

    # Security enforcement truth table (first-class section)
    parts.append("SECURITY ENFORCEMENT STATUS")
    parts.extend(enforcement_lines)
    parts.append("")

    # Sandbox tool coverage (M5: env shaping, classification, dispatch scope)
    parts.append("SANDBOX TOOL COVERAGE")
    parts.extend(coverage_lines)
    parts.append("")

    # Backend validity
    parts.append("BACKEND VALIDITY")
    parts.extend(backend_lines)
    parts.append("")

    # Operator risk notes (always shown, even if empty section)
    parts.append("OPERATOR NOTES")
    if risk_lines:
        parts.extend(risk_lines)
    else:
        parts.append("  No operator risk notes.")
    parts.append("")

    return DoctorReport(text="\n".join(parts), exit_code=exit_code)


# ---------------------------------------------------------------------------
# Output directory diagnostics
# ---------------------------------------------------------------------------

#: Core artifacts required for a run to be considered complete.
_CORE_ARTIFACTS: list[tuple[str, str]] = [
    ("effective_config.json", "effective_config"),
    ("audit_trail.jsonl", "audit_trail"),
    ("synthesis.md", "synthesis"),
    ("report.html", "report_html"),
    ("metrics.json", "metrics"),
    ("knowledge_base.md", "knowledge_base"),
    ("results.tsv", "results"),
]

#: The minimum set of artifacts whose absence turns health to WARNING.
_REQUIRED_FOR_HEALTH = {"effective_config", "synthesis", "report_html"}


def _read_metrics(metrics_path: Path) -> tuple[float | None, str | None]:
    """Return (best_score, run_status) from metrics.json, or (None, None)."""
    import json

    if not metrics_path.exists():
        return None, None
    try:
        data = json.loads(metrics_path.read_text(encoding="utf-8"))
        return data.get("best_score"), data.get("run_status")
    except (json.JSONDecodeError, OSError):
        return None, None


def _classify_run(
    iteration_count: int,
    has_synthesis: bool,
    has_report: bool,
) -> tuple[str, list[str]]:
    """Return (classification_label, warning_list)."""
    warnings: list[str] = []

    if iteration_count == 0:
        warnings.append("No iteration files found — run may not have started or is corrupt.")
        return "empty / no iterations", warnings

    if not has_synthesis and not has_report:
        warnings.append(
            f"Run has {iteration_count} iteration(s) but no synthesis or report"
            " — interrupted before synthesis phase."
        )
        return "partial (no synthesis)", warnings

    if has_synthesis and not has_report:
        warnings.append(
            "Synthesis present but report.html missing — report generation incomplete."
        )
        return "partial (synthesis only)", warnings

    return "complete", warnings


def _read_last_workflow_transition(audit_trail_path: Path) -> dict | None:
    """Return the last ``workflow_transition`` event from *audit_trail_path*.

    Returns ``None`` if the file is absent, unreadable, or has no such events.
    Pure filesystem read — no side effects.
    """
    import json

    if not audit_trail_path.exists():
        return None
    try:
        text = audit_trail_path.read_text(encoding="utf-8")
    except OSError:
        return None

    last: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event") == "workflow_transition":
            last = event
    return last


def _workflow_state_lines(
    last_transition: dict | None,
) -> tuple[list[str], list[str]]:
    """Return (section_lines, issues) for the WORKFLOW STATE doctor section.

    *issues* is non-empty when the workflow state requires operator attention:
    - ``paused_for_human`` — pending human gate, run cannot auto-resume
    - ``interrupted``     — terminal failure; run ended abnormally
    - non-terminal active phase — workflow history inconsistent with artifact
      completeness (run looks done but workflow was never closed)

    Both outputs contribute to the overall health/exit-code decision.
    """
    from .workflows.contracts import get_contract

    _TERMINAL: frozenset[str] = frozenset({"converged", "interrupted"})
    _PAUSE: frozenset[str] = frozenset({"paused_for_human"})

    lines: list[str] = ["WORKFLOW STATE"]
    workflow_issues: list[str] = []

    if last_transition is None:
        lines.append("  (no workflow history found in audit trail)")
        lines.append("")
        return lines, workflow_issues

    workflow = last_transition.get("workflow", "unknown")
    to_state = last_transition.get("to_state", "unknown")
    is_terminal = to_state in _TERMINAL
    is_paused = to_state in _PAUSE
    is_active = not is_terminal and not is_paused

    lines.append(f"  workflow:     {workflow}")
    lines.append(f"  last_phase:   {to_state}")

    if to_state == "interrupted":
        lines.append("  terminal:     yes (interrupted)")
        lines.append("  pending_gate: no")
        workflow_issues.append("Workflow terminated with interrupted state — run ended abnormally.")
    elif to_state == "converged":
        lines.append("  terminal:     yes (converged)")
        lines.append("  pending_gate: no")
    elif is_paused:
        lines.append("  terminal:     no")
        lines.append("  pending_gate: YES — human review required before resuming")
        workflow_issues.append("Workflow paused for human review — run cannot auto-resume.")
    else:
        # Non-terminal active phase
        lines.append("  terminal:     no")
        lines.append("  pending_gate: no")
        contract = get_contract(workflow, to_state)
        if contract is not None:
            lines.append(f"  recovery_mode: {contract.recovery_mode}")
        else:
            lines.append("  recovery_mode: unknown (no contract for this phase)")
        workflow_issues.append(
            f"Workflow state '{to_state}' is non-terminal — "
            "run history may be incomplete or the workflow was interrupted mid-phase."
        )

    lines.append("")
    return lines, workflow_issues


def doctor_output_text(output_dir: Path) -> DoctorReport:
    """Inspect *output_dir* and return a DoctorReport for the run state.

    Checks:
    - Core artifact completeness
    - Resumability integrity (iteration files present)
    - Synthesis/report regeneration readiness
    - Partial/corrupt run classification

    Pure filesystem inspection — no backends, no dirs created, no network.

    Args:
        output_dir: Output directory of a previous run.

    Returns:
        DoctorReport with text and exit_code (0=healthy, 1=warnings/errors).
    """
    from src.run_paths import RunPaths

    if not output_dir.exists():
        text = f"HEALTH: ERROR\n\n  [ERROR] Output directory not found: {output_dir}\n"
        return DoctorReport(text=text, exit_code=1)

    paths = RunPaths.for_output_dir(output_dir)

    # Collect artifact presence
    artifact_status: dict[str, bool] = {}
    for label, attr in _CORE_ARTIFACTS:
        path = getattr(paths, attr)
        artifact_status[attr] = path.exists()

    # Iteration files
    iter_files = (
        sorted(paths.iterations_dir.glob("iter_*.md"))
        if paths.iterations_dir.exists()
        else []
    )
    iteration_count = len(iter_files)

    best_score, run_status = _read_metrics(paths.metrics)

    # Classify run state
    run_class, run_warnings = _classify_run(
        iteration_count=iteration_count,
        has_synthesis=artifact_status["synthesis"],
        has_report=artifact_status["report_html"],
    )

    # Required artifact warnings
    issues: list[str] = list(run_warnings)
    for attr in _REQUIRED_FOR_HEALTH:
        if not artifact_status.get(attr, False):
            fname = next(lbl for lbl, a in _CORE_ARTIFACTS if a == attr)
            issues.append(f"Required artifact missing: {fname}")

    health = "OK" if not issues else f"WARNINGS ({len(issues)} issue{'s' if len(issues) != 1 else ''})"
    exit_code = 0 if not issues else 1

    parts: list[str] = []
    parts.append(f"output: {output_dir.resolve()}")
    parts.append("")
    parts.append(f"HEALTH: {health}")
    parts.append(f"  run classification: {run_class}")
    if run_status:
        parts.append(f"  run_status:         {run_status}")
    if best_score is not None:
        parts.append(f"  best_score:         {best_score}")
    parts.append("")

    # Artifact status
    parts.append("ARTIFACT STATUS")
    iter_label = (
        f"iterations ({iteration_count} files)" if iteration_count > 0
        else "iterations (none found)"
    )
    iter_mark = "✓" if iteration_count > 0 else "✗"
    parts.append(f"  {iter_mark} {iter_label}")
    for label, attr in _CORE_ARTIFACTS:
        mark = "✓" if artifact_status[attr] else "✗"
        parts.append(f"  {mark} {label}")
    parts.append("")

    # Resumability
    can_resume = iteration_count > 0 and not (artifact_status["synthesis"] and artifact_status["report_html"])
    parts.append("RESUMABILITY")
    parts.append(f"  resumable:        {'yes' if can_resume else 'no'}")
    parts.append(f"  iterations_found: {iteration_count}")
    if can_resume:
        reusable: list[str] = []
        reusable.append(f"{iteration_count} iteration file(s) (iter_*.md)")
        if artifact_status.get("knowledge_base", False):
            reusable.append("knowledge_base.md")
        if artifact_status.get("results", False):
            reusable.append("results.tsv")
        if reusable:
            parts.append("  reused on resume: " + ", ".join(reusable))
        else:
            parts.append("  reused on resume: (nothing recoverable beyond iteration files)")
    parts.append("")

    # Synthesis readiness
    parts.append("SYNTHESIS READINESS")
    synthesis_ready = iteration_count > 0 and artifact_status.get("effective_config", False)
    parts.append(
        f"  can regenerate synthesis: {'yes' if synthesis_ready else 'no'}"
    )
    if not synthesis_ready:
        if iteration_count == 0:
            parts.append("  [!] No iteration data — cannot regenerate synthesis.")
        if not artifact_status.get("effective_config", False):
            parts.append("  [!] effective_config.json missing — config context unavailable.")
    parts.append("")

    # Workflow state (from audit trail) — may add issues that affect health
    last_transition = _read_last_workflow_transition(paths.audit_trail)
    workflow_lines, workflow_issues = _workflow_state_lines(last_transition)
    issues.extend(workflow_issues)

    # Re-derive health after workflow issues are merged
    health = "OK" if not issues else f"WARNINGS ({len(issues)} issue{'s' if len(issues) != 1 else ''})"
    exit_code = 0 if not issues else 1

    # Patch the HEALTH line already added to parts
    for i, line in enumerate(parts):
        if line.startswith("HEALTH:"):
            parts[i] = f"HEALTH: {health}"
            break

    parts.extend(workflow_lines)

    # Warnings section
    if issues:
        parts.append("WARNINGS")
        for issue in issues:
            parts.append(f"  [!] {issue}")
        parts.append("")

    return DoctorReport(text="\n".join(parts), exit_code=exit_code)


def doctor_config_from_path(config_path: Path) -> DoctorReport:
    """Load config from *config_path* and run doctor_config_text.

    Handles parse failures gracefully (exit_code=1, error text).

    Args:
        config_path: Path to the research config YAML.

    Returns:
        DoctorReport — exit_code=1 if the file cannot be parsed.
    """
    from src.config import ResearchConfig

    try:
        config = ResearchConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        text = (
            f"HEALTH: ERROR\n\n"
            f"  [ERROR] Failed to load config: {exc}\n"
        )
        return DoctorReport(text=text, exit_code=1)

    return doctor_config_text(config)
