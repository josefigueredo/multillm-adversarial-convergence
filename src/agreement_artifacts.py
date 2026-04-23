"""Helpers for inter-rater agreement artifact persistence."""

from __future__ import annotations

import json
from typing import Any

from .scorer import compute_inter_rater_agreement


def write_agreement_artifact(researcher: Any) -> None:
    """Compute and persist inter-rater agreement when multi-candidate data exists."""
    agreement = compute_inter_rater_agreement(researcher._candidate_assessments)
    if agreement["dimensions_with_multiple_candidates"] > 0:
        agreement_path = researcher.output_dir / "agreement.json"
        agreement_path.write_text(json.dumps(agreement, indent=2), encoding="utf-8")
