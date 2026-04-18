"""ConvergeStrategy — standalone multi-LLM document convergence strategy.

NOT a Strategy subclass and NOT registered in _STRATEGY_REGISTRY.
Used exclusively by DocumentRefiner.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("autoresearch")

from .backends import AgentResponse, Backend, CallOptions
from .config import DocumentConfig
from .hitl import DeferReason, HumanDecision, HumanInputRequest
from .prompts import render

# (prompt, backend_obj, backend_name) -> AgentResponse
InvokeFn = Callable[[str, Backend, str], AgentResponse]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RawCritique:
    """A critique from the Challenger or a persona (not yet verified)."""

    description: str
    section_ref: str
    raised_by: str


@dataclass
class VerifiedCritique:
    """A critique classified by the Verifier."""

    description: str
    section_ref: str
    raised_by: str
    status: str             # "valid" | "stale" | "deferred"
    defer_reason: str | None = None
    question: str | None = None
    suggested_answer: str | None = None


@dataclass
class Patch:
    """A patch proposal from the Arbitrator."""

    section_ref: str
    proposed_text: str
    rationale: str


# ---------------------------------------------------------------------------
# ConvergeStrategy
# ---------------------------------------------------------------------------

class ConvergeStrategy:
    """Orchestrates the 5-step document convergence cycle.

    Standalone — does NOT extend Strategy and is NOT in _STRATEGY_REGISTRY.
    """

    def __init__(self, config: DocumentConfig, backends: dict[str, Backend]) -> None:
        self._config = config
        research = config.backends.research
        primary = config.backends.primary

        builder_name = research[0] if research else primary
        challenger_name = research[1] if len(research) > 1 else primary
        verifier_name = config.backends.utility_or_primary
        arbitrator_name = config.backends.judge_or_primary

        def _get(name: str) -> tuple[Backend, str]:
            backend = backends.get(name) or backends[primary]
            return backend, name

        self._builder, self._builder_name = _get(builder_name)
        self._challenger, self._challenger_name = _get(challenger_name)
        self._verifier, self._verifier_name = _get(verifier_name)
        self._arbitrator, self._arbitrator_name = _get(arbitrator_name)
        self._persona_backend, self._persona_name = backends[primary], primary

    # ── Source file injection ────────────────────────────────────────────────

    def _source_block(self, role: str) -> str:
        """Return formatted Markdown block of source files visible to `role`."""
        matching = [sf for sf in self._config.source_files if role in sf.roles]
        if not matching:
            return ""
        parts = []
        for sf in matching:
            try:
                content = Path(sf.path).read_text(encoding="utf-8")
            except OSError:
                log.warning("source_files: could not read %s — skipping", sf.path)
                continue
            parts.append(f"### {sf.path}\n\n{content}")
        return "\n\n---\n\n".join(parts)

    # ── Builder ─────────────────────────────────────────────────────────────

    def run_builder(
        self,
        prd: str,
        patches: list[Patch],
        invoke: InvokeFn,
        *,
        human_decisions: list[HumanDecision],
    ) -> str:
        """Generate the initial PRD (cycle 1) or apply validated patches (cycle N+)."""
        human_block = _format_human_decisions(human_decisions)
        patches_block = _format_patches(patches)
        prompt = render(
            "prd_builder.md",
            topic=self._config.topic,
            goal=self._config.goal,
            source_material=self._config.source_material,
            source_files=self._source_block("builder"),
            current_prd=prd,
            patches=patches_block,
            human_decisions=human_block,
        )
        resp = invoke(prompt, self._builder, self._builder_name)
        return resp.text

    # ── Challenger ──────────────────────────────────────────────────────────

    def run_challenger(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run internal consistency critique. Returns list of raw critiques."""
        prompt = render(
            "prd_challenger.md",
            prd=prd,
            topic=self._config.topic,
            source_files=self._source_block("challenger"),
        )
        resp = invoke(prompt, self._challenger, self._challenger_name)
        return _parse_raw_critiques(resp.text, default_raised_by="challenger")

    # ── Personas ────────────────────────────────────────────────────────────

    def run_personas(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run all personas. Parallel or serial per config.persona_mode."""
        if self._config.persona_mode == "parallel":
            return self._run_personas_parallel(prd, invoke)
        return self._run_personas_serial(prd, invoke)

    def _run_personas_parallel(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        with ThreadPoolExecutor(max_workers=len(self._config.personas)) as pool:
            futures = {
                pool.submit(self._invoke_persona, persona, prd, invoke): persona
                for persona in self._config.personas
            }
            for future in as_completed(futures):
                results.extend(future.result())
        return results

    def _run_personas_serial(self, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        for persona in self._config.personas:
            results.extend(self._invoke_persona(persona, prd, invoke))
        return results

    def _invoke_persona(self, persona: Any, prd: str, invoke: InvokeFn) -> list[RawCritique]:
        prompt_file = persona.prompt_file or f"prd_persona_{persona.name}.md"
        prompt = render(
            prompt_file,
            prd=prd,
            topic=self._config.topic,
            source_files=self._source_block(persona.name),
        )
        resp = invoke(prompt, self._persona_backend, self._persona_name)
        return _parse_raw_critiques(resp.text, default_raised_by=persona.name)

    # ── Verifier ────────────────────────────────────────────────────────────

    def run_verifier(
        self, prd: str, critiques: list[RawCritique], invoke: InvokeFn
    ) -> list[VerifiedCritique]:
        """Classify each critique as valid / stale / deferred."""
        if not critiques:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref, "raised_by": c.raised_by}
             for c in critiques],
            indent=2,
        )
        prompt = render("prd_verify.md", prd=prd, critiques_json=critiques_json)
        resp = invoke(prompt, self._verifier, self._verifier_name)
        return _parse_verified_critiques(resp.text)

    # ── Arbitrator ──────────────────────────────────────────────────────────

    def run_arbitrator(
        self, prd: str, critiques: list[VerifiedCritique], invoke: InvokeFn
    ) -> list[Patch]:
        """Generate patch proposals for all VALID critiques."""
        valid = [c for c in critiques if c.status == "valid"]
        if not valid:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref}
             for c in valid],
            indent=2,
        )
        prompt = render("prd_arbitrate.md", prd=prd, valid_critiques_json=critiques_json)
        resp = invoke(prompt, self._arbitrator, self._arbitrator_name)
        return _parse_patches(resp.text)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Any:
    """Extract JSON from model output (tolerates markdown fences)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    bracket = text.find("[")
    if bracket != -1:
        return json.loads(text[bracket:])
    return json.loads(text)


def _parse_raw_critiques(text: str, *, default_raised_by: str) -> list[RawCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        RawCritique(
            description=item.get("description", ""),
            section_ref=item.get("section_ref", ""),
            raised_by=item.get("raised_by", default_raised_by),
        )
        for item in items
        if isinstance(item, dict) and item.get("description")
    ]


def _parse_verified_critiques(text: str) -> list[VerifiedCritique]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        VerifiedCritique(
            description=item.get("description", ""),
            section_ref=item.get("section_ref", ""),
            raised_by=item.get("raised_by", ""),
            status=item.get("status", "stale"),
            defer_reason=item.get("defer_reason"),
            question=item.get("question"),
            suggested_answer=item.get("suggested_answer"),
        )
        for item in items
        if isinstance(item, dict)
    ]


def _parse_patches(text: str) -> list[Patch]:
    try:
        items = _extract_json(text)
    except (json.JSONDecodeError, ValueError):
        return []
    return [
        Patch(
            section_ref=item.get("section_ref", ""),
            proposed_text=item.get("proposed_text", ""),
            rationale=item.get("rationale", ""),
        )
        for item in items
        if isinstance(item, dict) and item.get("proposed_text")
    ]


def _format_human_decisions(decisions: list[HumanDecision]) -> str:
    if not decisions:
        return ""
    lines = ["--- HUMAN DECISIONS (ground truth — do not contradict) ---\n"]
    for d in decisions:
        lines.append(f"[{d.issue_id}] {d.question}\n  Answer: {d.answer}\n")
    lines.append("---")
    return "\n".join(lines)


def _format_patches(patches: list[Patch]) -> str:
    if not patches:
        return "(no patches — generate initial document)"
    lines = []
    for i, p in enumerate(patches, 1):
        lines.append(f"Patch {i} [{p.section_ref}]: {p.proposed_text}\nRationale: {p.rationale}")
    return "\n\n".join(lines)
