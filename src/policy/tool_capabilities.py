"""Tool capability classification for policy-aware sandbox dispatch.

Provides an explicit, testable map from tool names to their capability
dimensions.  This replaces scattered ad-hoc name checks (``if tool == "Bash"``,
``_WEB_TOOL_NAMES``) with a single authoritative classification layer.

Design contract
---------------
- :data:`_TOOL_CAPABILITIES` is the registry of known tools.  All tools that
  appear in ``execution.allowed_tools`` should be classified here.
- :data:`SHIPPED_TOOLS` is the public frozenset of all tool names this repo
  officially recognises.  It mirrors the registry keys and serves as the
  canonical source-of-truth for coverage checks.
- :func:`classify_tool` returns ``None`` for unknown tools — callers are
  responsible for deciding how to treat unclassified tools (typically: deny
  conservatively when sandbox is active).
- :func:`coverage_stats` reports classification coverage for an arbitrary list
  of tool names, surfacing registry gaps without raising exceptions.
- :func:`check_capability_consistency` validates that a single
  :class:`ToolCapabilities` record is internally coherent (e.g. network tools
  must declare a destination type).
- :class:`ToolCapabilities` is immutable (frozen dataclass).  Classification
  output is stable across multiple calls.

Capability dimensions
---------------------
- ``uses_host_shell``:  Tool may invoke arbitrary host-shell commands
  (e.g. ``Bash``).
- ``uses_network``:     Tool makes outbound network requests.
- ``destination_type``: ``"web"`` for HTTP/HTTPS endpoints, ``"other"``
  for any other network destination, ``None`` when no network is used.
  Valid values: ``None``, ``"web"``, ``"other"``.
- ``may_write``:        Tool may write or mutate files on the filesystem.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


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

    # Directory listing (read-only, no network, no shell)
    "LS": ToolCapabilities(),
}


#: Public frozenset of all tool names this repo officially recognises.
#:
#: Mirrors the registry keys and serves as the canonical source-of-truth for
#: coverage checks.  Update :data:`_TOOL_CAPABILITIES` first when adding a new
#: tool — this constant is derived from it.
SHIPPED_TOOLS: frozenset[str] = frozenset(_TOOL_CAPABILITIES.keys())


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


# ---------------------------------------------------------------------------
# Coverage diagnostics
# ---------------------------------------------------------------------------

#: Valid values for :attr:`ToolCapabilities.destination_type`.
_VALID_DESTINATION_TYPES: frozenset[str | None] = frozenset({None, "web", "other"})


def coverage_stats(
    tool_names: Iterable[str],
) -> dict[str, Any]:
    """Return a classification coverage summary for *tool_names*.

    The result is a plain dict with the following keys:

    - ``total`` — number of tool names examined.
    - ``classified`` — tools found in :data:`_TOOL_CAPABILITIES`.
    - ``unclassified`` — tools **not** found in the registry.
    - ``unclassified_names`` — ordered list of unclassified tool names,
      preserving the input iteration order.

    Parameters
    ----------
    tool_names:
        An iterable of canonical tool name strings.  Generators are
        consumed exactly once.

    Returns
    -------
    dict[str, Any]
        Coverage summary.
    """
    total = 0
    classified = 0
    unclassified_names: list[str] = []
    for name in tool_names:
        total += 1
        if name in _TOOL_CAPABILITIES:
            classified += 1
        else:
            unclassified_names.append(name)
    return {
        "total": total,
        "classified": classified,
        "unclassified": total - classified,
        "unclassified_names": unclassified_names,
    }


def check_capability_consistency(caps: ToolCapabilities) -> list[str]:
    """Return a list of internal consistency errors for *caps*.

    An empty list means *caps* is coherent.  Non-empty means at least one
    invariant is violated.

    Rules enforced:

    1. If ``uses_network`` is ``True``, ``destination_type`` must be a
       recognised non-``None`` value (``"web"`` or ``"other"``).
    2. If ``uses_network`` is ``False``, ``destination_type`` must be ``None``.
    3. ``destination_type`` must be one of the valid values:
       ``None``, ``"web"``, ``"other"``.

    Parameters
    ----------
    caps:
        The :class:`ToolCapabilities` record to validate.

    Returns
    -------
    list[str]
        Human-readable error messages.  Empty when *caps* is consistent.
    """
    errors: list[str] = []

    if caps.destination_type not in _VALID_DESTINATION_TYPES:
        errors.append(
            f"destination_type {caps.destination_type!r} is not a valid value; "
            f"must be one of {sorted(str(v) for v in _VALID_DESTINATION_TYPES if v is not None) + [None]!r}"  # noqa: E501
        )
        # Still check the network/destination relationship below using the raw value.

    if caps.uses_network and caps.destination_type is None:
        errors.append(
            "destination_type must not be None when uses_network is True"
        )
    elif not caps.uses_network and caps.destination_type is not None:
        errors.append(
            f"destination_type should be None when uses_network is False, "
            f"got {caps.destination_type!r}"
        )

    return errors
