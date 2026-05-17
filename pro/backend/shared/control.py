"""Pure logic for applying a control patch to a state.

Kept in its own module so both the local server and the Lambda control
handler call the same function. No I/O lives here — easy to unit-test.
"""

from __future__ import annotations

from typing import Any, Mapping

from .state import BroadcastState

ALLOWED_FIELDS = {
    "view",
    "deck_id",
    "slide",
    "glossary_term",
    "glossary_language",
    "demo_id",
    "demo_step",
    "dashboard_id",
}


def apply_patch(current: BroadcastState, patch: Mapping[str, Any]) -> BroadcastState:
    """Validate the patch keys, then return the bumped state.

    Unknown keys are rejected (rather than silently dropped) so a typo on
    the presenter side surfaces immediately instead of becoming a confusing
    no-op for every viewer.
    """

    unknown = set(patch) - ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"unknown fields in control patch: {sorted(unknown)}")
    return current.bumped(**dict(patch))
