"""Human-in-the-loop intervention policy types and parsing.

Self-contained leaf module — no other config submodule imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VALID_INTERVENTION_MODES: tuple[str, ...] = (
    "full_auto",
    "checkpoint_only",
    "decision_only",
    "co_pilot",
    "step_review",
)


@dataclass(frozen=True)
class HitlConfig:
    """Human-in-the-loop workflow intervention policy.

    Attributes:
        intervention_mode: Controls when human review gates activate.

            ``full_auto``       — fully automated; no human gates triggered.
            ``checkpoint_only`` — pause at major workflow checkpoints
                                  (e.g. end-of-phase, convergence).
            ``decision_only``   — pause at critical decision points
                                  (e.g. keep/discard, critique verdict).
            ``co_pilot``        — pause before each phase execution so a
                                  human can review context and steer.
            ``step_review``     — pause after each phase for review before
                                  the next phase begins.
    """

    intervention_mode: str = "full_auto"


def _parse_hitl_config(raw: dict[str, Any]) -> HitlConfig:
    """Parse and validate a ``hitl:`` mapping."""
    mode = raw.get("intervention_mode", "full_auto")
    if mode not in VALID_INTERVENTION_MODES:
        raise ValueError(
            f"Invalid hitl.intervention_mode '{mode}'. "
            f"Must be one of: {', '.join(VALID_INTERVENTION_MODES)}"
        )
    return HitlConfig(intervention_mode=mode)
