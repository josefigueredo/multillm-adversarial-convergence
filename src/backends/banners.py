"""Shared CLI quota / rate-limit banner detection.

When a CLI adapter's stdout looks like an account-level banner (out of
usage, rate limited, quota exceeded) rather than real model output, the
research loop must reject it as ``is_error=True`` — otherwise the
banner text lands in ``knowledge_base.md`` as findings.

Patterns are anchored to the start of the normalized text so legitimate
research findings that mention phrases like "the API hit a usage limit
during the benchmark" are NOT dropped — only banners that *begin* with
the marker phrase match.

Bypass via env var ``RESEARCH_DISABLE_BANNER_FILTER=1`` if a legitimate
finding is being dropped.
"""

from __future__ import annotations

import os
import re

_QUOTA_BANNER_PATTERNS = (
    re.compile(r"^you'?re out of (extra )?usage", re.IGNORECASE),
    re.compile(r"^claude (code )?usage limit", re.IGNORECASE),
    re.compile(r"^usage limit (reached|exceeded)", re.IGNORECASE),
    re.compile(r"^quota exceeded", re.IGNORECASE),
    re.compile(r"^rate limit (exceeded|reached|hit)", re.IGNORECASE),
    re.compile(r"^you have been rate limited", re.IGNORECASE),
    re.compile(r"^rate limited\b", re.IGNORECASE),
)


def looks_like_quota_banner(text: str) -> bool:
    """Return true for CLI/account banners that are not usable model output.

    Empty / whitespace-only text counts as a banner (no usable content).
    """
    if os.environ.get("RESEARCH_DISABLE_BANNER_FILTER") == "1":
        return False
    normalized = " ".join(text.split()).lstrip()
    if not normalized:
        return True
    return any(pat.search(normalized) for pat in _QUOTA_BANNER_PATTERNS)
