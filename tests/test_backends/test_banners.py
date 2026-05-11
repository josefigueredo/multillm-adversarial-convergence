"""Tests for src.backends.banners — the shared quota/rate-limit detector.

Pins the contract every backend parser depends on:
- empty or whitespace-only text is treated as a banner (no usable content);
- the 7 anchored patterns match at the start of the normalized text only;
- legitimate findings that mention "rate limit" or "usage limit" inline are
  NOT dropped;
- RESEARCH_DISABLE_BANNER_FILTER=1 short-circuits everything to False.
"""

import os
from unittest.mock import patch

import pytest

from src.backends.banners import looks_like_quota_banner


class TestEmptyAndWhitespace:
    @pytest.mark.parametrize("text", ["", "   ", "\n\n", "\t \t"])
    def test_empty_or_whitespace_is_banner(self, text):
        assert looks_like_quota_banner(text) is True


class TestAnchoredPatterns:
    """Every shipping banner pattern must match at the start of the text."""

    @pytest.mark.parametrize("text", [
        "You're out of usage. Resets at 8pm.",
        "you're out of extra usage. resets later.",
        "Youre out of usage right now",  # no apostrophe variant
        "Claude usage limit reached",
        "Claude Code usage limit exceeded; try again in 1 hour",
        "Usage limit reached for sonnet",
        "Usage limit exceeded — please upgrade",
        "Quota exceeded for this account",
        "Rate limit exceeded for this org",
        "Rate limit reached on opus",
        "Rate limit hit; backoff 30s",
        "You have been rate limited by the API.",
        "Rate limited. Try again later.",
    ])
    def test_anchored_banner_phrases_match(self, text):
        assert looks_like_quota_banner(text) is True


class TestFalsePositiveGuards:
    """Real findings that *mention* quota terms inline must NOT be flagged."""

    @pytest.mark.parametrize("text", [
        "The API hit a usage limit during the benchmark run, see appendix.",
        "Findings: when the user is rate limited, the gateway returns 429.",
        "AWS API Gateway enforces a quota exceeded behavior via X-RateLimit headers.",
        "Discussion: how to detect rate limit hit conditions in client code.",
        # Banner-shaped phrases buried in normal prose:
        "We compared two approaches: one where quota exceeded triggers retry, "
        "another where the client backs off.",
    ])
    def test_inline_mentions_are_not_banners(self, text):
        assert looks_like_quota_banner(text) is False

    def test_normal_prose_is_not_a_banner(self):
        assert looks_like_quota_banner("Here is a real finding about caching.") is False

    def test_short_unrelated_text_is_not_a_banner(self):
        assert looks_like_quota_banner("OK") is False


class TestNormalization:
    """The filter normalizes leading whitespace/newlines before matching."""

    def test_leading_whitespace_does_not_evade_filter(self):
        assert looks_like_quota_banner("   \n  Rate limit exceeded") is True

    def test_internal_whitespace_is_collapsed(self):
        # Internal multiple spaces shouldn't break the match.
        assert looks_like_quota_banner("Rate    limit   exceeded") is True


class TestBypassEnvVar:
    """RESEARCH_DISABLE_BANNER_FILTER=1 must short-circuit before any pattern check."""

    def test_bypass_disables_filter(self):
        with patch.dict(os.environ, {"RESEARCH_DISABLE_BANNER_FILTER": "1"}):
            assert looks_like_quota_banner("Rate limit exceeded") is False
            assert looks_like_quota_banner("") is False

    def test_bypass_only_when_explicitly_one(self):
        for val in ("0", "true", "yes", "", " 1 "):
            with patch.dict(os.environ, {"RESEARCH_DISABLE_BANNER_FILTER": val}):
                assert looks_like_quota_banner("Rate limit exceeded") is True, (
                    f"expected filter active for env value {val!r}"
                )
