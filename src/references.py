"""Deterministic references assembly for paper output.

Builds a stable, deduplicated References section from tracked citations
artifacts rather than relying on LLM-generated citation lists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Query parameters that are purely tracking noise and should be stripped
# when normalizing URLs for deduplication.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "referrer",
    }
)

# Heading patterns that mark an existing references/bibliography block.
# Exported as ``REFS_HEADING_RE`` so other modules (e.g. citation_verification)
# can share the same compiled pattern without duplicating the rule.
REFS_HEADING_RE = re.compile(
    r"^#{1,6}\s+(References|Bibliography)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_REFS_HEADING_RE = REFS_HEADING_RE  # internal alias preserved for backward compat


# ---------------------------------------------------------------------------
# URL normalization
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Return a canonical form of *url* suitable for deduplication.

    Transformations applied:
    - Lowercase scheme and host
    - Strip trailing slash from the path (unless the path is exactly ``/``)
    - Drop the fragment identifier
    - Remove known tracking query parameters
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    path = parsed.path
    if path.endswith("/"):
        path = path.rstrip("/")  # strips all trailing slashes, including lone "/"

    # Filter tracking params from query string
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        clean_qs = {k: v for k, v in qs.items() if k not in _TRACKING_PARAMS}
        query = urlencode(clean_qs, doseq=True) if clean_qs else ""
    else:
        query = ""

    # Drop fragment entirely
    fragment = ""

    normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
    return normalized


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def dedupe_citations(citations: list[dict]) -> list[dict]:
    """Return a deduplicated list, keeping only URL-bearing citations.

    - Local-file-only citations (no ``url`` field) are excluded.
    - When two records share the same normalized URL, the one with a non-empty
      title is preferred; otherwise the first occurrence wins.
    - Original insertion order is preserved among distinct URLs.
    """
    seen: dict[str, dict] = {}  # normalized_url -> best record so far
    order: list[str] = []  # normalized_url insertion order

    for citation in citations:
        url = citation.get("url", "")
        if not url:
            continue  # local-path-only — exclude
        key = normalize_url(url)
        if key not in seen:
            seen[key] = citation
            order.append(key)
        else:
            existing = seen[key]
            if not existing.get("title") and citation.get("title"):
                seen[key] = citation  # upgrade to titled record

    return [seen[k] for k in order]


# ---------------------------------------------------------------------------
# References section builder
# ---------------------------------------------------------------------------


def build_references_section(citations: list[dict]) -> str:
    """Build a Markdown references block from *citations*.

    Returns an empty string when no URL-bearing citations exist after
    deduplication (graceful no-op for runs with no web citations).
    """
    deduped = dedupe_citations(citations)
    if not deduped:
        return ""

    lines = ["## References", ""]
    for i, citation in enumerate(deduped, start=1):
        url = citation.get("url", "")
        title = (citation.get("title") or "").strip()
        if title:
            lines.append(f"{i}. [{title}]({url})")
        else:
            lines.append(f"{i}. {url}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Injection into existing Markdown
# ---------------------------------------------------------------------------


def inject_references_section(markdown: str, references_block: str) -> str:
    """Append or replace a References/Bibliography section in *markdown*.

    If *references_block* is empty, *markdown* is returned unchanged.
    If an existing heading matching ``References`` or ``Bibliography`` is found,
    only that section (up to the next heading of the same or higher level) is
    replaced — preserving any appendices or content that follows.
    Otherwise the block is appended.
    """
    if not references_block:
        return markdown

    match = _REFS_HEADING_RE.search(markdown)
    if match:
        heading_start = match.start()
        heading_level = len(match.group(0).split()[0])  # count leading '#'

        # Find the next heading of equal or higher level after this one
        next_heading_re = re.compile(
            r"^#{1," + str(heading_level) + r"}\s+\S",
            re.MULTILINE,
        )
        after_heading = markdown[match.end() :]
        next_match = next_heading_re.search(after_heading)

        if next_match:
            # Replace only the References section; preserve what follows
            following = after_heading[next_match.start() :]
            prefix = markdown[:heading_start].rstrip("\n")
            return prefix + "\n\n" + references_block + "\n" + following
        else:
            # References is the last section — replace to EOF
            return markdown[:heading_start].rstrip("\n") + "\n\n" + references_block
    else:
        sep = "" if markdown.endswith("\n\n") else ("\n" if markdown.endswith("\n") else "\n\n")
        return markdown + sep + references_block


# ---------------------------------------------------------------------------
# Filesystem integration
# ---------------------------------------------------------------------------


def generate_references_for_synthesis(
    synthesis_path: Path,
    citations_path: Path,
) -> str:
    """Load citations from *citations_path*, inject into *synthesis_path*, return final text.

    Graceful no-ops:
    - Missing *citations_path* → return original synthesis text unchanged.
    - Missing *synthesis_path* → return empty string.
    """
    if not synthesis_path.exists():
        return ""

    original = synthesis_path.read_text(encoding="utf-8")

    if not citations_path.exists():
        return original

    try:
        citations = json.loads(citations_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return original

    refs_block = build_references_section(citations)
    final = inject_references_section(original, refs_block)

    if final != original:
        synthesis_path.write_text(final, encoding="utf-8")

    return final
