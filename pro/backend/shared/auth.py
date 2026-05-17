"""API key authentication.

The presenter endpoint takes an ``X-API-Key`` header. Comparison is
constant-time to avoid leaking key prefixes via timing.
"""

from __future__ import annotations

import hmac
from typing import Optional


class ApiKeyMismatch(Exception):
    """Raised when the provided API key does not match the expected value."""


def require_api_key(provided: Optional[str], expected: str) -> None:
    if not expected:
        raise ApiKeyMismatch("server has no API key configured")
    if not provided or not hmac.compare_digest(provided, expected):
        raise ApiKeyMismatch("invalid or missing API key")
