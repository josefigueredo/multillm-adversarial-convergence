"""Tool capability classification for policy-aware sandbox dispatch.

Provides an explicit, testable map from tool names to their capability
dimensions.  This replaces scattered ad-hoc name checks (``if tool == "Bash"``,
``_WEB_TOOL_NAMES``) with a single authoritative classification layer.

Design contract
---------------
- :data:`_TOOL_CAPABILITIES` is the registry of known tools.  All tools that
  appear in ``execution.allowed_tools`` should be classified here.
- :func:`classify_tool` returns ``None`` for unknown tools — callers are
  responsible for deciding how to treat unclassified tools (typically: deny
  conservatively when sandbox is active).
- :class:`ToolCapabilities` is immutable (frozen dataclass).  Classification
  output is stable across multiple calls.

Capability dimensions
---------------------
- ``uses_host_shell``:  Tool may invoke arbitrary host-shell commands
  (e.g. ``Bash``).
- ``uses_network``:     Tool makes outbound network requests.
- ``destination_type``: ``"web"`` for HTTP/HTTPS endpoints, ``"other"``
  for any other network destination, ``None`` when no network is used.
- ``may_write``:        Tool may write or mutate files on the filesystem.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Capability dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolCapabilities:
    """Declared capability dimensions for a single tool.

    All fields default to the most conservative (least-privileged) value so
    that a tool with no special capabilities can be expressed as
    ``ToolCapabilities()`` without any arguments.
    """

    uses_host_shell: bool = False
    """True when the tool can invoke arbitrary shell commands on the host."""

    uses_network: bool = False
    """True when the tool makes outbound network connections."""

    destination_type: str | None = None
    """Network destination category: ``"web"`` (HTTP/HTTPS), ``"other"``,
    or ``None`` when :attr:`uses_network` is ``False``."""

    may_write: bool = False
    """True when the tool may create or modify files on the filesystem."""


# ---------------------------------------------------------------------------
# Tool capability registry
# ---------------------------------------------------------------------------

#: Registry mapping canonical tool names to their declared capabilities.
#:
#: Add new entries here when new tools are introduced.  Unknown tools are
#: **not** in this registry; :func:`classify_tool` returns ``None`` for them.
_TOOL_CAPABILITIES: dict[str, ToolCapabilities] = {
    # Host-shell access
    "Bash": ToolCapabilities(
        uses_host_shell=True,
        may_write=True,
    ),

    # Network — web destinations
    "WebSearch": ToolCapabilities(
        uses_network=True,
        destination_type="web",
    ),
    "WebFetch": ToolCapabilities(
        uses_network=True,
        destination_type="web",
    ),

    # Filesystem reads (no write, no network, no shell)
    "Read": ToolCapabilities(),
    "Glob": ToolCapabilities(),
    "Grep": ToolCapabilities(),

    # Filesystem writes
    "Write": ToolCapabilities(may_write=True),
    "Edit": ToolCapabilities(may_write=True),
    "MultiEdit": ToolCapabilities(may_write=True),

    # Task/agent tools (no special capabilities at dispatch level)
    "TodoRead": ToolCapabilities(),
    "TodoWrite": ToolCapabilities(may_write=True),
    "Task": ToolCapabilities(),
}


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def classify_tool(tool_name: str) -> ToolCapabilities | None:
    """Return the declared capabilities for *tool_name*, or ``None`` if unknown.

    Tool name matching is **case-sensitive** — ``"Bash"`` and ``"bash"`` are
    different tools.  Unknown tools return ``None``; callers should treat
    unknown tools conservatively (e.g. deny when sandbox is active).

    Parameters
    ----------
    tool_name:
        Canonical name of the tool (e.g. ``"WebSearch"``, ``"Bash"``).

    Returns
    -------
    ToolCapabilities | None
        Capability record for the tool, or ``None`` when the tool is not in
        :data:`_TOOL_CAPABILITIES`.
    """
    return _TOOL_CAPABILITIES.get(tool_name)


def classify_allowed_tools(
    tool_names: Iterable[str],
) -> list[tuple[str, ToolCapabilities | None]]:
    """Classify a collection of tool names preserving input order.

    Parameters
    ----------
    tool_names:
        An iterable of canonical tool name strings.

    Returns
    -------
    list[tuple[str, ToolCapabilities | None]]
        A list of ``(tool_name, capabilities)`` pairs.  ``capabilities`` is
        ``None`` for unrecognised tools.
    """
    return [(name, classify_tool(name)) for name in tool_names]
