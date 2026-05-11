"""Pure text utilities shared across the research loop and resume state.

Extracted from research_loop.py to break the circular dependency with
run_state.py — both modules need ``canonical_topic`` for gap dedup but
run_state previously imported it lazily from a private name on
research_loop. These helpers depend on nothing but ``re`` and
``difflib``, so any module can pull from here.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

# Two-or-more-token co-occurrence of these words flags Spanish content.
# Frozenset rather than a regex because we score per-token, not match-text.
# Threshold (2 hits with at least 4 tokens) catches observed Spanish noise
# without false-positives on English that happens to include a loan-word.
_SPANISH_STOPWORDS = frozenset({
    "de", "la", "el", "los", "las", "una", "uno", "por", "con", "del",
    "para", "como", "que", "es", "en", "se", "lo", "al", "su", "sus",
    "y", "o", "pero", "este", "esta", "estos", "estas", "no",
})


def looks_spanish(topic: str) -> bool:
    """Return True if ``topic`` reads as Spanish via a stop-word heuristic.

    Avoids a langdetect dependency for this minimal need.
    """
    tokens = re.findall(r"\b[a-záéíóúñü]+\b", topic.lower())
    if len(tokens) < 4:
        return False
    spanish_hits = sum(1 for t in tokens if t in _SPANISH_STOPWORDS)
    return spanish_hits >= 2


def canonical_topic(topic: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation.

    Used as a hash for duplicate detection across iterations and on resume.
    """
    cleaned = re.sub(r"\s+", " ", topic.strip()).strip(".:;,!?\"'`")
    return cleaned.lower()


def edit_distance_ratio(a: str, b: str) -> float:
    """Cheap Levenshtein-style similarity ratio in [0, 1].

    Returns 1.0 for identical strings, lower for divergent. Uses difflib
    from stdlib to avoid a new dependency.
    """
    return SequenceMatcher(a=a, b=b).ratio()
