"""Single source of truth for what every viewer sees.

The whole protocol is one object. Adding a feature = adding a field.
Clients ignore unknown fields, so older clients keep working when the
server gains new capabilities. `version` is a monotonic counter — clients
discard messages older than what they already have.
"""

from __future__ import annotations

import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

View = Literal["deck", "glossary", "demo", "dashboard"]


class BroadcastState(BaseModel):
    """The complete view state that every connected client mirrors."""

    view: View = "deck"
    deck_id: str = "deck.html"
    slide: int = 1

    glossary_term: Optional[str] = None
    glossary_language: Optional[str] = None

    demo_id: str = "shell-demo.html"
    demo_step: int = 0

    dashboard_id: str = "dashboard-for-slide.html"

    version: int = 0
    # Epoch SECONDS, not milliseconds: DynamoDB rejects native floats, and
    # we don't need sub-second precision for "when did the state last change."
    updated_at: int = Field(default_factory=lambda: int(time.time()))

    def bumped(self, **patch) -> "BroadcastState":
        """Return a new state with the patch applied + version incremented.

        Pydantic's ``model_copy(update=...)`` only swaps the listed fields,
        so version monotonicity is guaranteed regardless of which subset of
        fields a caller wants to change.
        """

        return self.model_copy(
            update={
                **patch,
                "version": self.version + 1,
                "updated_at": int(time.time()),
            }
        )
