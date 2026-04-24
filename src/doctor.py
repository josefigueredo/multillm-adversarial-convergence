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
# Security enforcement truth table (Milestone 2 ground-truth)
# ---------------------------------------------------------------------------

#: Fields that are *actively enforced* in runtime code (AutoResearcher).
_ENFORCED: dict[str, str] = {
    "allow_host_bash": "hard-blocks Bash tool in _call_with",
    "sandbox.filesystem_access": "explicit write gate via guard_path_write",
    "allow_filesystem_write_outside_output": "broadens write boundary in is_write_allowed",
}

#: Fields that are *declared in config* but not yet OS/kernel-enforced.
_DECLARED_ONLY: dict[str, str] = {
    "tool_execution_mode: sandboxed": "requires a real sandbox backend (not yet implemented)",
    "sandbox.network_access": "not enforced at OS level; treat as audit-mode only",
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
    lines: list[str] = []

    lines.append("  Field                                   Status")
    lines.append("  " + "-" * 66)

    # always enforced
    bash_status = "ENFORCED" if not sec.allow_host_bash else "ENFORCED (allow_host_bash=true → Bash permitted)"
    lines.append(f"  {'allow_host_bash':<39} {bash_status}")
    lines.append(f"  {'sandbox.filesystem_access':<39} ENFORCED  (guard_path_write)")
    lines.append(
        f"  {'allow_filesystem_write_outside_output':<39} "
        f"{'ENFORCED  (broadens write roots)' if sec.allow_filesystem_write_outside_output else 'ENFORCED  (default: output_only)'}"
    )

    # declared-only
    if sec.tool_execution_mode == "sandboxed":
        lines.append(
            f"  {'tool_execution_mode: sandboxed':<39} declared-only  (requires real sandbox backend)"
        )
    else:
        lines.append(
            f"  {'tool_execution_mode: direct':<39} direct  (no sandbox layer)"
        )

    net_label = f"sandbox.network_access: {sb.network_access}"
    lines.append(f"  {net_label:<39} declared-only  (not OS-enforced)")
    lines.append(f"  {'content_trust':<39} declared-only  (not yet runtime-evaluated)")
    return lines


def _risk_note_lines(config: "ResearchConfig") -> tuple[list[str], list[str]]:
    """Return (note_lines, issues) for operator warnings.

    Every risk note is also added to *issues* so that it drives exit_code = 1.
    """
    sec = config.security
    tools = _parse_tools(config.execution.allowed_tools)
    notes: list[str] = []
    issues: list[str] = []

    if sec.allow_host_bash and "Bash" in tools:
        msg = (
            "allow_host_bash is true AND Bash is in allowed_tools"
            " — host shell is exposed to the agent."
        )
        notes.append(f"  [!] {msg}")
        issues.append(msg)

    if (
        sec.tool_execution_mode == "sandboxed"
        and sec.sandbox.mode == "tool_calls"
    ):
        msg = (
            "sandbox declared (tool_execution_mode=sandboxed, mode=tool_calls)"
            " but not yet OS-enforced — treat as audit-mode declaration only."
        )
        notes.append(f"  [!] {msg}")
        issues.append(msg)

    if sec.sandbox.network_access != "unrestricted":
        msg = (
            f"sandbox.network_access={sec.sandbox.network_access}"
            " is declared but not enforced at the OS level."
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
