"""Trust classification model for claims and provenance artifacts.

Trust classes answer "where did this come from?" — distinct from
source quality (which answers "how reliable is it?").

- ``trusted_local_config``         — loaded from operator-controlled config on disk
- ``trusted_generated_artifact``   — produced deterministically by the framework itself
- ``untrusted_web_content``        — fetched from external URLs (any source type)
- ``untrusted_tool_output``        — raw output from agent tool calls (Bash, Grep, etc.)
- ``user_provided_source_material``— supplied directly by the user
- ``inferred_claim``               — synthesised/inferred by an LLM from other evidence
"""

from __future__ import annotations

from typing import Any


#: Full set of valid trust class labels.
TRUST_CLASSES: frozenset[str] = frozenset(
    {
        "trusted_local_config",
        "trusted_generated_artifact",
        "untrusted_web_content",
        "untrusted_tool_output",
        "user_provided_source_material",
        "inferred_claim",
    }
)


def classify_citation_trust(citation: dict[str, Any]) -> str:
    """Return the trust class for a citation record.

    - Records with a local ``path`` (no ``url``) are ``user_provided_source_material``
      — they come from operator-supplied files injected into agent prompts.
    - All URL-based citations are ``untrusted_web_content`` regardless of source
      quality tier (even ``official_docs`` or ``paper`` types are fetched from
      external sources the framework does not control).

    Args:
        citation: A citation dict containing ``url`` and/or ``path``.

    Returns:
        A member of :data:`TRUST_CLASSES`.
    """
    if citation.get("path") and not citation.get("url"):
        return "user_provided_source_material"
    return "untrusted_web_content"


def classify_claim_trust(claim: dict[str, Any]) -> str:
    """Return the trust class for a claim record.

    All claims produced by the research loop are LLM-synthesised inferences
    and are therefore classified as ``inferred_claim``.

    Args:
        claim: A claim dict (may contain ``claim_type``, ``text``, etc.).

    Returns:
        A member of :data:`TRUST_CLASSES`.
    """
    return "inferred_claim"


def trust_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate a list of trust-labelled items into a count per class.

    Items without a ``trust_class`` key are silently skipped.

    Args:
        items: List of dicts each optionally containing ``trust_class``.

    Returns:
        Mapping of trust class → count, omitting classes with zero count.

    Example::

        trust_summary([
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "untrusted_web_content"},
            {"trust_class": "inferred_claim"},
        ])
        # → {"untrusted_web_content": 2, "inferred_claim": 1}
    """
    counts: dict[str, int] = {}
    for item in items:
        label = item.get("trust_class")
        if label is not None:
            counts[label] = counts.get(label, 0) + 1
    return counts
