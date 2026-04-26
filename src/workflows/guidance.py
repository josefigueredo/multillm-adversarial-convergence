"""Structured HITL guidance persistence and injection — MM08 Step 3.

Human guidance is captured when a workflow pauses at a :class:`~src.workflows.gates.HitlGate`
and a reviewer provides input.  Each :class:`HitlGuidance` record is persisted
to ``{output_dir}/hitl_guidance.jsonl`` by :class:`GuidanceStore` and can be
retrieved for injection into the next phase via :func:`format_guidance_block`.

Guidance types
--------------
``steer``
    The reviewer provides a direction or constraint for the next phase.

``approve``
    The reviewer approves the current output and authorizes continuation.

``reject``
    The reviewer rejects the current output and requests a redo.

``annotate``
    The reviewer adds notes or observations without directing behavior.

Usage
-----
::

    from src.workflows.guidance import GuidanceStore, HitlGuidance, format_guidance_block
    from src.workflows.gates import GateTrigger, GateTarget

    # Persist guidance when a human provides input at a gate
    store = GuidanceStore(output_dir)
    guidance = HitlGuidance(
        workflow="research",
        target="hypothesis",
        target_type=GateTarget.PHASE,
        gate_trigger=GateTrigger.BEFORE,
        guidance_type="steer",
        guidance_text="Focus on TCO comparisons, not just purchase price.",
        sequence=0,
    )
    store.save(guidance)

    # Retrieve and inject into the next phase prompt
    relevant = store.load_for_target("research", "hypothesis", GateTrigger.BEFORE)
    context_block = format_guidance_block(relevant)
    # prepend context_block to the phase prompt
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.workflows.gates import GateTarget, GateTrigger, VALID_WORKFLOWS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_GUIDANCE_TYPES: tuple[str, ...] = ("steer", "approve", "reject", "annotate")
GUIDANCE_FILENAME = "hitl_guidance.jsonl"


# ---------------------------------------------------------------------------
# HitlGuidance dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HitlGuidance:
    """One human guidance record produced at a workflow gate pause.

    Attributes
    ----------
    workflow:
        The workflow in which this gate fired — ``"research"``, ``"refine"``,
        or ``"plan"``.
    target:
        The phase name or checkpoint name at which the gate fired.  Matches
        :attr:`~src.workflows.gates.HitlGate.target`.
    target_type:
        Whether *target* is a :attr:`~src.workflows.gates.GateTarget.PHASE` or
        a :attr:`~src.workflows.gates.GateTarget.CHECKPOINT`.
    gate_trigger:
        Whether the gate fired :attr:`~src.workflows.gates.GateTrigger.BEFORE`
        or :attr:`~src.workflows.gates.GateTrigger.AFTER` the target.
    guidance_type:
        Semantic classification of the guidance: ``"steer"``, ``"approve"``,
        ``"reject"``, or ``"annotate"``.
    guidance_text:
        Free-form human input.
    sequence:
        Gate-firing ordinal for repeated gates (same target can fire multiple
        times across iterations/cycles).  Defaults to ``0``.
    timestamp:
        UTC ISO-8601 timestamp, auto-generated at construction.
    """

    workflow: str
    target: str
    target_type: str
    gate_trigger: str
    guidance_type: str
    guidance_text: str
    sequence: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.workflow not in VALID_WORKFLOWS:
            raise ValueError(
                f"Invalid workflow: {self.workflow!r}. "
                f"Must be one of: {', '.join(VALID_WORKFLOWS)}"
            )
        try:
            GateTrigger(self.gate_trigger)
        except ValueError:
            raise ValueError(
                f"Invalid gate_trigger: {self.gate_trigger!r}. "
                f"Must be one of: {', '.join(t.value for t in GateTrigger)}"
            )
        try:
            GateTarget(self.target_type)
        except ValueError:
            raise ValueError(
                f"Invalid target_type: {self.target_type!r}. "
                f"Must be one of: {', '.join(t.value for t in GateTarget)}"
            )
        if self.guidance_type not in VALID_GUIDANCE_TYPES:
            raise ValueError(
                f"Invalid guidance_type: {self.guidance_type!r}. "
                f"Must be one of: {', '.join(VALID_GUIDANCE_TYPES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict."""
        return {
            "workflow": self.workflow,
            "target": self.target,
            "target_type": self.target_type,
            "gate_trigger": self.gate_trigger,
            "guidance_type": self.guidance_type,
            "guidance_text": self.guidance_text,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HitlGuidance":
        """Deserialise from a JSON-decoded dict.

        Raises
        ------
        KeyError
            If a required field is missing.
        ValueError
            If a field value fails validation.
        """
        return cls(
            workflow=data["workflow"],
            target=data["target"],
            target_type=data["target_type"],
            gate_trigger=data["gate_trigger"],
            guidance_type=data["guidance_type"],
            guidance_text=data["guidance_text"],
            sequence=int(data.get("sequence", 0)),
            timestamp=data["timestamp"],
        )


# ---------------------------------------------------------------------------
# GuidanceStore
# ---------------------------------------------------------------------------


class GuidanceStore:
    """Append-only JSONL store for :class:`HitlGuidance` records.

    Records are persisted to ``{output_dir}/hitl_guidance.jsonl``, one JSON
    object per line.  Corrupt or schema-invalid lines are skipped silently on
    read so that a single bad record never prevents access to the rest.

    Parameters
    ----------
    output_dir:
        Directory containing the run's output artifacts.  Created automatically
        by :meth:`save` if it does not yet exist.
    """

    def __init__(self, output_dir: Path) -> None:
        self._path = output_dir / GUIDANCE_FILENAME

    def save(self, guidance: HitlGuidance) -> None:
        """Append *guidance* to the JSONL file, creating it if necessary."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(guidance.to_dict(), ensure_ascii=False) + "\n")

    def load_all(self) -> list[HitlGuidance]:
        """Return all valid guidance records in append order.

        Silently skips lines that are not valid JSON or that fail
        :meth:`HitlGuidance.from_dict` validation.
        """
        if not self._path.exists():
            return []
        records: list[HitlGuidance] = []
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(HitlGuidance.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    pass  # skip corrupt or schema-invalid records
        return records

    def load_for_target(
        self,
        workflow: str,
        target: str,
        gate_trigger: "GateTrigger | str",
        *,
        sequence: int | None = None,
    ) -> list[HitlGuidance]:
        """Return guidance records matching *workflow*, *target*, and *gate_trigger*.

        Parameters
        ----------
        workflow:
            One of ``"research"``, ``"refine"``, ``"plan"``.
        target:
            Phase name or checkpoint name.
        gate_trigger:
            :attr:`~src.workflows.gates.GateTrigger.BEFORE` or
            :attr:`~src.workflows.gates.GateTrigger.AFTER`.
        sequence:
            If provided, only records with this sequence number are returned.
            ``None`` (default) returns all matching records across all sequences.
        """
        trigger = GateTrigger(gate_trigger)  # validates and normalises to enum
        return [
            g for g in self.load_all()
            if (
                g.workflow == workflow
                and g.target == target
                and g.gate_trigger == trigger  # str-enum equality: "before" == GateTrigger.BEFORE
                and (sequence is None or g.sequence == sequence)
            )
        ]

    def load_latest(self) -> "HitlGuidance | None":
        """Return the last valid appended record, or ``None`` if the store is empty.

        "Latest" is defined as the last valid line in append order, not the
        record with the largest timestamp.
        """
        records = self.load_all()
        return records[-1] if records else None


# ---------------------------------------------------------------------------
# Prompt injection helper
# ---------------------------------------------------------------------------


def format_guidance_block(guidance_list: list[HitlGuidance]) -> str:
    """Format a list of guidance records as a structured block for prompt injection.

    The returned string is meant to be prepended to a phase prompt so the
    model has explicit human context before generating its response.

    Returns an empty string for an empty input list (graceful no-op, safe to
    prepend unconditionally).

    Parameters
    ----------
    guidance_list:
        Guidance records to include, typically from
        :meth:`GuidanceStore.load_for_target`.
    """
    if not guidance_list:
        return ""
    parts = ["## Human Guidance"]
    for g in guidance_list:
        header = f"\n### {g.guidance_type.capitalize()} ({g.target}, {g.gate_trigger})"
        parts.append(header)
        parts.append(g.guidance_text.strip())
    return "\n".join(parts)
