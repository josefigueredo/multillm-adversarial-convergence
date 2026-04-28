"""ImplementStrategy — adversarial builder/challenger/verifier/arbitrator for code tasks.

MM09: Safe Adversarial Implement Mode — Step 3.

Follows the same ``InvokeFn`` injection pattern as ConvergeStrategy and
PlanStrategy.  All four phase methods accept an ``invoke`` keyword-only
argument so the runner can inject the tracked backend call wrapper, keeping
the strategy testable without real LLM connections.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.implement.document_strategy import InvokeFn, _extract_json
from src.implement.implement_loop import (
    CandidatePatch,
    ImplementConfig,
    ImplementCritique,
    ImplementTarget,
    ImplementTask,
    VerifiedImplementCritique,
)
from src.prompts import render

log = logging.getLogger("autoresearch")


class ImplementStrategy:
    """Adversarial strategy for code implementation tasks.

    Roles:
    - Builder     — generates or improves the candidate patch.
    - Challenger  — critiques the patch for correctness/regressions.
    - Verifier    — classifies each critique (valid / stale).
    - Arbitrator  — produces a revised patch from valid critiques.

    All phase methods receive explicit ImplementTarget context so policy
    constraints can be enforced later (Step 4).
    """

    def __init__(self, config: ImplementConfig, backends: dict[str, Any]) -> None:
        self._config = config
        self._backends = backends

    def run_builder(
        self,
        task: ImplementTask,
        target: ImplementTarget,
        *,
        last_patch: CandidatePatch | None = None,
        accepted_critiques: list[VerifiedImplementCritique] | None = None,
        invoke: InvokeFn,
    ) -> CandidatePatch:
        """Generate or improve a candidate patch."""
        accepted = accepted_critiques or []
        accepted_block = _format_accepted_critiques(accepted)
        last_patch_block = (
            last_patch.content if last_patch
            else "(no prior patch — generate initial implementation)"
        )
        prompt = render(
            "implement_builder.md",
            task_description=task.description,
            target_path=str(target.path),
            execution_level=target.execution_level,
            allowed_roots=(
                ", ".join(str(r) for r in target.allowed_roots)
                or "(all — no roots restricted)"
            ),
            last_patch=last_patch_block,
            accepted_critiques=accepted_block,
        )
        backend_name, backend = self._primary_backend()
        resp = invoke(prompt, backend, backend_name)
        return _parse_implement_patch(resp.text if hasattr(resp, "text") else str(resp))

    def run_challenger(
        self,
        patch: CandidatePatch,
        task: ImplementTask,
        target: ImplementTarget,
        *,
        invoke: InvokeFn,
    ) -> list[ImplementCritique]:
        """Critique *patch* for correctness, regressions, and architecture fit."""
        prompt = render(
            "implement_challenger.md",
            task_description=task.description,
            patch_content=patch.content,
            touched_files=", ".join(patch.touched_files) or "(not specified)",
            target_path=str(target.path),
        )
        backend_name, backend = self._primary_backend()
        resp = invoke(prompt, backend, backend_name)
        return _parse_implement_critiques(resp.text if hasattr(resp, "text") else str(resp))

    def run_verifier(
        self,
        patch: CandidatePatch,
        critiques: list[ImplementCritique],
        task: ImplementTask,
        target: ImplementTarget,
        *,
        invoke: InvokeFn,
    ) -> list[VerifiedImplementCritique]:
        """Classify each critique as ``valid`` or ``stale``."""
        if not critiques:
            return []
        critiques_json = json.dumps(
            [
                {
                    "description": c.description,
                    "file_ref": c.file_ref,
                    "raised_by": c.raised_by,
                }
                for c in critiques
            ],
            indent=2,
        )
        prompt = render(
            "implement_verify.md",
            task_description=task.description,
            patch_content=patch.content,
            critiques_json=critiques_json,
        )
        backend_name, backend = self._primary_backend()
        resp = invoke(prompt, backend, backend_name)
        return _parse_verified_implement_critiques(
            resp.text if hasattr(resp, "text") else str(resp)
        )

    def run_arbitrator(
        self,
        patch: CandidatePatch,
        valid_critiques: list[VerifiedImplementCritique],
        task: ImplementTask,
        target: ImplementTarget,
        *,
        invoke: InvokeFn,
    ) -> CandidatePatch:
        """Produce a revised patch that addresses all *valid_critiques*."""
        critiques_json = json.dumps(
            [{"description": c.description, "file_ref": c.file_ref} for c in valid_critiques],
            indent=2,
        )
        prompt = render(
            "implement_arbitrate.md",
            task_description=task.description,
            patch_content=patch.content,
            valid_critiques_json=critiques_json,
            target_path=str(target.path),
        )
        backend_name, backend = self._primary_backend()
        resp = invoke(prompt, backend, backend_name)
        return _parse_implement_patch(resp.text if hasattr(resp, "text") else str(resp))

    def _primary_backend(self) -> tuple[str, Any]:
        if not self._backends:
            raise RuntimeError(
                "ImplementStrategy requires at least one backend to be configured"
            )
        name = next(iter(self._backends))
        return name, self._backends[name]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_implement_critiques(text: str) -> list[ImplementCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [
        ImplementCritique(
            description=item.get("description", ""),
            file_ref=item.get("file_ref", ""),
            raised_by=item.get("raised_by", "challenger"),
        )
        for item in items
        if isinstance(item, dict) and item.get("description")
    ]


def _parse_verified_implement_critiques(text: str) -> list[VerifiedImplementCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    return [
        VerifiedImplementCritique(
            description=item.get("description", ""),
            file_ref=item.get("file_ref", ""),
            raised_by=item.get("raised_by", ""),
            status=item.get("status", "stale"),
        )
        for item in items
        if isinstance(item, dict)
    ]


def _parse_implement_patch(text: str) -> CandidatePatch:
    """Extract a CandidatePatch from LLM output.

    Tries JSON first ({"content": "...", "rationale": "..."}), then falls
    back to treating the whole response as the patch content.
    """
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            obj = json.loads(fenced.group(1))
            return CandidatePatch(
                content=obj.get("content", text),
                rationale=obj.get("rationale", ""),
                touched_files=tuple(obj.get("touched_files", [])),
            )
        except (json.JSONDecodeError, ValueError):
            pass
    brace = text.find("{")
    if brace != -1:
        try:
            obj = json.loads(text[brace:])
            return CandidatePatch(
                content=obj.get("content", text),
                rationale=obj.get("rationale", ""),
                touched_files=tuple(obj.get("touched_files", [])),
            )
        except (json.JSONDecodeError, ValueError):
            pass
    return CandidatePatch(content=text)


def _format_accepted_critiques(critiques: list[VerifiedImplementCritique]) -> str:
    if not critiques:
        return "(none — generate or maintain the current patch)"
    lines = ["--- ACCEPTED CRITIQUES (must be addressed in the new patch) ---\n"]
    for i, c in enumerate(critiques, 1):
        lines.append(f"{i}. [{c.file_ref}] {c.description}")
    lines.append("---")
    return "\n".join(lines)
