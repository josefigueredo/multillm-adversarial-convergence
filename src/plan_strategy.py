"""PlanStrategy — standalone multi-LLM plan convergence strategy.

NOT a Strategy subclass and NOT registered in _STRATEGY_REGISTRY.
Used exclusively by PlanRefiner.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .backends import Backend
from .config import PlanConfig
from .document_strategy import (
    InvokeFn,
    Patch,
    RawCritique,
    VerifiedCritique,
    _format_human_decisions,
    _parse_patches,
    _parse_raw_critiques,
    _parse_verified_critiques,
)
from .hitl import HumanDecision
from .prompts import render
from .workflows.decisions import CritiqueStatus

log = logging.getLogger("autoresearch")


def _format_plan_patches(patches: list[Patch]) -> str:
    if not patches:
        return "(no patches — generate initial plan)"
    lines = []
    for i, p in enumerate(patches, 1):
        lines.append(f"Patch {i} [{p.section_ref}]: {p.proposed_text}\nRationale: {p.rationale}")
    return "\n\n".join(lines)


class PlanStrategy:
    """Orchestrates the 5-step plan convergence cycle.

    Standalone — does NOT extend Strategy and is NOT in _STRATEGY_REGISTRY.
    """

    def __init__(self, config: PlanConfig, backends: dict[str, Backend]) -> None:
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
        """Return a formatted Markdown block of source files visible to *role*.

        Files are read lazily on each call (no caching), so changes on disk
        between cycles are picked up automatically.

        Returns an empty string when no files match *role* — callers can inject
        this directly into prompt templates without checking for emptiness first.
        The ``## Reference Files`` heading is included in the return value only
        when at least one file is readable, preventing empty sections in prompts.

        Unreadable files (permission errors, deleted between config load and
        invocation) are logged as warnings and skipped rather than aborting the run.
        """
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
        if not parts:
            return ""
        return "## Reference Files\n\n" + "\n\n---\n\n".join(parts)

    # ── Builder ─────────────────────────────────────────────────────────────

    def run_builder(
        self,
        plan: str,
        patches: list[Patch],
        invoke: InvokeFn,
        *,
        human_decisions: list[HumanDecision],
        guidance_context: str = "",
    ) -> str:
        """Generate the initial plan (cycle 1) or apply validated patches (cycle N+)."""
        human_block = _format_human_decisions(human_decisions)
        patches_block = _format_plan_patches(patches)
        prompt = render(
            "plan_builder.md",
            topic=self._config.topic,
            goal=self._config.goal,
            source_material=self._config.source_material,
            source_files=self._source_block("builder"),
            current_plan=plan,
            patches=patches_block,
            human_decisions=human_block,
        )
        if guidance_context:
            prompt = guidance_context + "\n\n---\n\n" + prompt
        resp = invoke(prompt, self._builder, self._builder_name)
        return resp.text

    # ── Challenger ──────────────────────────────────────────────────────────

    def run_challenger(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run structural gap critique. Returns list of raw critiques."""
        prompt = render(
            "plan_challenger.md",
            plan=plan,
            topic=self._config.topic,
            source_files=self._source_block("challenger"),
        )
        resp = invoke(prompt, self._challenger, self._challenger_name)
        return _parse_raw_critiques(resp.text, default_raised_by="challenger")

    # ── Personas ────────────────────────────────────────────────────────────

    def run_personas(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        """Run all personas. Parallel or serial per config.persona_mode."""
        if self._config.persona_mode == "parallel":
            return self._run_personas_parallel(plan, invoke)
        return self._run_personas_serial(plan, invoke)

    def _run_personas_parallel(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        with ThreadPoolExecutor(max_workers=len(self._config.personas)) as pool:
            futures = {
                pool.submit(self._invoke_persona, persona, plan, invoke): persona
                for persona in self._config.personas
            }
            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception as exc:
                    persona = futures[future]
                    log.warning("plan_strategy: persona '%s' raised an error — skipping: %s", persona.name, exc)
        return results

    def _run_personas_serial(self, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        results: list[RawCritique] = []
        for persona in self._config.personas:
            results.extend(self._invoke_persona(persona, plan, invoke))
        return results

    def _invoke_persona(self, persona: Any, plan: str, invoke: InvokeFn) -> list[RawCritique]:
        prompt_file = persona.prompt_file or f"plan_persona_{persona.name}.md"
        try:
            prompt = render(
                prompt_file,
                plan=plan,
                topic=self._config.topic,
                source_files=self._source_block(persona.name),
            )
        except FileNotFoundError:
            log.warning("plan_strategy: prompt file not found for persona '%s' — skipping", persona.name)
            return []
        resp = invoke(prompt, self._persona_backend, self._persona_name)
        return _parse_raw_critiques(resp.text, default_raised_by=persona.name)

    # ── Verifier ────────────────────────────────────────────────────────────

    def run_verifier(
        self, plan: str, critiques: list[RawCritique], invoke: InvokeFn
    ) -> list[VerifiedCritique]:
        """Classify each critique as valid / stale / deferred."""
        if not critiques:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref,
              "raised_by": c.raised_by}
             for c in critiques],
            indent=2,
        )
        prompt = render("plan_verify.md", plan=plan, critiques_json=critiques_json)
        resp = invoke(prompt, self._verifier, self._verifier_name)
        return _parse_verified_critiques(resp.text)

    # ── Arbitrator ──────────────────────────────────────────────────────────

    def run_arbitrator(
        self, plan: str, critiques: list[VerifiedCritique], invoke: InvokeFn
    ) -> list[Patch]:
        """Generate patch proposals for all VALID critiques."""
        valid = [c for c in critiques if c.status == CritiqueStatus.VALID]
        if not valid:
            return []
        critiques_json = json.dumps(
            [{"description": c.description, "section_ref": c.section_ref}
             for c in valid],
            indent=2,
        )
        prompt = render(
            "plan_arbitrate.md", plan=plan, valid_critiques_json=critiques_json
        )
        resp = invoke(prompt, self._arbitrator, self._arbitrator_name)
        return _parse_patches(resp.text)
