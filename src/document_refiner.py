"""DocumentRefiner — document convergence orchestrator.

Sibling to AutoResearcher. Runs Phase 1 (PRD convergence),
Phase 2 (artifact expansion), and Phase 3 (index generation).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backends import AgentResponse, Backend
from .backend_options import apply_backend_capabilities, build_call_options
from .audit_trail import AuditTrailWriter
from .config import ArtifactConfig, DocumentConfig, ProviderConfig
from .document_loop import CycleContext, CycleState, _should_stop, run_cycle
from .document_strategy import ConvergeStrategy
from .hitl import (
    append_human_decisions,
    load_human_decisions,
    write_pending_questions,
)
from .prompts import render

from .workflows.refine_states import RefineState
from .workflows.transitions import WorkflowTransitionEmitter
from .workflows.guidance import GUIDANCE_FILENAME, GuidanceStore, format_guidance_block
from .workflows.gates import GateTrigger
from .workflows.review_packet import (
    REVIEW_PACKET_FILENAME,
    build_review_packet,
    write_review_packet,
)

log = logging.getLogger("autoresearch")

EXIT_HUMAN_REQUIRED = 2
_LAST_PAUSE_FILE = "last_pause.json"


class DocumentRefiner:
    """Orchestrates a document convergence run (refine subcommand).

    Phase 1 — Convergence: PRD refined through adversarial cycles until clean.
    Phase 2 — Expansion: Execution and companion artifacts generated from
               the converged PRD, each optionally reviewed.
    Phase 3 — Indexing: DOCS_INDEX.md and README.md auto-generated.
    """

    def __init__(
        self,
        config: DocumentConfig,
        output_dir: Path,
        backends: dict[str, Backend],
        resume: bool = False,
    ) -> None:
        self._config = config
        self._output_dir = output_dir
        self._run_dir = output_dir / ".run"
        self._backends = backends
        self._resume = resume
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._audit_trail = AuditTrailWriter(output_dir / "audit_trail.jsonl", mode="refine", run_id=output_dir.name)

    # ── Public entry point ──────────────────────────────────────────────────

    def run(self, *, interactive: bool = True) -> int:
        """Run all three phases. Returns exit code (0 on success, 2 on HITL pause)."""
        self._setup_dirs()

        strategy = ConvergeStrategy(self._config, self._backends)
        state = self._init_state()

        guidance_context = ""
        if self._resume:
            pause_file = self._run_dir / _LAST_PAUSE_FILE
            if pause_file.exists():
                meta = json.loads(pause_file.read_text(encoding="utf-8"))
                sequence = meta.get("cycle")
                store = GuidanceStore(self._output_dir)
                records = store.load_for_target(
                    "refine", "verifier", GateTrigger.AFTER, sequence=sequence
                )
                guidance_context = format_guidance_block(records)

        ctx = CycleContext(
            call_with=self._invoke,
            invoke_for_strategy=self._invoke,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            config=self._config,
            human_decisions=state.human_decisions,
            read_prd_section=lambda ref: "",
            update_issue_registry=lambda issues: None,
            audit_trail=self._audit_trail,
            artifact_root=self._output_dir,
            guidance_context=guidance_context,
        )

        self._audit_trail.emit(
            "run_started",
            primary_artifact=self._config.primary_artifact,
            resume=self._resume,
        )

        # Phases 1–3 and finalization wrapped together so that CONVERGED is
        # only emitted on true end-to-end completion and INTERRUPTED is emitted
        # for failures in any phase.
        try:
            # Phase 1 — Convergence
            while not _should_stop(state, self._config):
                valid_count, stale_count, deferred_count = run_cycle(
                    state, ctx, strategy, interactive=interactive
                )
                log.info(
                    "[cycle %d] valid=%d stale=%d deferred=%d clean_streak=%d",
                    state.cycle, valid_count, stale_count, deferred_count,
                    state.consecutive_clean_cycles,
                )
                self._write_cycle_snapshot(state)
                self._write_issue_registry(state)

                if state.human_decisions:
                    decisions_path = self._run_dir / "human_decisions.json"
                    append_human_decisions(state.human_decisions, decisions_path)

                if state.pending_human_inputs and not interactive:
                    self._handle_hitl_pause(state)
                    self._audit_trail.emit("run_paused_for_human_input", cycle=state.cycle)
                    return EXIT_HUMAN_REQUIRED

            # Write converged primary artifact
            self._write_primary_artifact(state.prd)
            log.info(
                "[refine] Phase 1 complete — %s converged in %d cycle(s).",
                self._config.primary_artifact, state.cycle,
            )

            # Phase 2 — Expansion
            self._run_phase2(state.prd, strategy, ctx)

            # Phase 3 — Indexing
            self._run_phase3()

            # Finalize
            self._write_run_manifest(cycles=state.cycle, total_cost=self._total_cost)
            self._audit_trail.emit("run_completed", cycles=state.cycle, status="completed")
            log.info("[refine] Done. Output at: %s", self._output_dir)
        except Exception:
            WorkflowTransitionEmitter(
                self._audit_trail, "refine", state.current_workflow_state
            ).transition(RefineState.INTERRUPTED, cycle=state.cycle)
            raise

        WorkflowTransitionEmitter(
            self._audit_trail, "refine", state.current_workflow_state
        ).transition(RefineState.CONVERGED, cycles=state.cycle)
        return 0

    # ── Phase 2: Expansion ──────────────────────────────────────────────────

    def _run_phase2(self, prd: str, strategy: ConvergeStrategy, ctx: CycleContext) -> None:
        for artifact in self._config.artifacts:
            log.info("[phase2] Generating %s ...", artifact.name)
            with self._audit_trail.step(
                "phase2_generate_artifact",
                artifact_root=self._output_dir,
                artifact=artifact.name,
                layer=artifact.layer,
            ):
                content = self._generate_artifact(prd, artifact, strategy, ctx)
                out_path = self._output_dir / artifact.name
                out_path.write_text(content, encoding="utf-8")
                log.info("[phase2] Wrote %s", artifact.name)

    def _generate_artifact(
        self,
        prd: str,
        artifact: ArtifactConfig,
        strategy: ConvergeStrategy,
        ctx: CycleContext,
    ) -> str:
        stem = Path(artifact.name).stem
        prompt_file = artifact.prompt_file or f"artifact_{stem}.md"
        try:
            prompt = render(prompt_file, prd=prd, topic=self._config.topic,
                            goal=self._config.goal)
        except FileNotFoundError:
            log.warning("Prompt file not found for %s — skipping generation.", artifact.name)
            return f"# {artifact.name}\n\n(prompt not configured)\n"

        builder_name = (
            self._config.backends.research[0]
            if self._config.backends.research
            else self._config.backends.primary
        )
        backend = self._backends.get(builder_name) or self._backends[self._config.backends.primary]
        resp = self._invoke(prompt, backend, builder_name)

        if artifact.review:
            content = resp.text
            raw = strategy.run_challenger(content, ctx.call_with)
            verified = strategy.run_verifier(content, raw, ctx.call_with)
            valid = [v for v in verified if v.status == "valid"]
            if valid:
                patches = strategy.run_arbitrator(content, valid, ctx.call_with)
                content = strategy.run_builder(
                    content, patches, ctx.call_with,
                    human_decisions=ctx.human_decisions,
                )
            return content

        return resp.text

    # ── Phase 3: Indexing ───────────────────────────────────────────────────

    def _run_phase3(self) -> None:
        with self._audit_trail.step("phase3_generate_indexes", artifact_root=self._output_dir):
            self._run_phase3_inner()

    def _run_phase3_inner(self) -> None:
        manifest = self._build_artifact_manifest()
        builder_name = (
            self._config.backends.research[0]
            if self._config.backends.research
            else self._config.backends.primary
        )
        backend = self._backends.get(builder_name) or self._backends[self._config.backends.primary]

        readme_resp = self._invoke(
            render(
                "generate_readme.md",
                topic=self._config.topic,
                goal=self._config.goal,
                primary_artifact=self._config.primary_artifact,
                artifact_manifest=manifest,
            ),
            backend,
            builder_name,
        )
        (self._output_dir / "README.md").write_text(readme_resp.text, encoding="utf-8")

        index_resp = self._invoke(
            render(
                "generate_docs_index.md",
                topic=self._config.topic,
                goal=self._config.goal,
                primary_artifact=self._config.primary_artifact,
                artifact_manifest=manifest,
                personas=", ".join(p.name for p in self._config.personas),
            ),
            backend,
            builder_name,
        )
        (self._output_dir / "DOCS_INDEX.md").write_text(index_resp.text, encoding="utf-8")

    def _build_artifact_manifest(self) -> str:
        lines = [f"- {self._config.primary_artifact} (primary, always present)"]
        for a in self._config.artifacts:
            lines.append(f"- {a.name} (layer:{a.layer}, review:{a.review})")
        lines.append("- DOCS_INDEX.md (auto-generated)")
        lines.append("- README.md (auto-generated)")
        return "\n".join(lines)

    # ── State management ────────────────────────────────────────────────────

    def _init_state(self) -> CycleState:
        state = CycleState(prd_path=Path(self._config.primary_artifact))
        if self._resume:
            decisions_path = self._run_dir / "human_decisions.json"
            state.human_decisions = load_human_decisions(decisions_path)
        return state

    def _setup_dirs(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "cycles").mkdir(exist_ok=True)

    def _write_primary_artifact(self, content: str) -> None:
        with self._audit_trail.step(
            "write_primary_artifact",
            artifact_root=self._output_dir,
            artifact=self._config.primary_artifact,
        ):
            (self._output_dir / self._config.primary_artifact).write_text(content, encoding="utf-8")

    def _write_cycle_snapshot(self, state: CycleState) -> None:
        with self._audit_trail.step(
            "write_cycle_snapshot",
            artifact_root=self._output_dir,
            cycle=state.cycle,
        ):
            snap = self._run_dir / "cycles" / f"cycle_{state.cycle:03d}.md"
            snap.write_text(
                f"# Cycle {state.cycle}\n\n"
                f"Valid issues: {sum(1 for i in state.issue_registry if i.status == 'valid')}\n"
                f"Clean streak: {state.consecutive_clean_cycles}\n\n"
                f"## PRD snapshot\n\n{state.prd[:2000]}\n",
                encoding="utf-8",
            )
            stem = Path(self._config.primary_artifact).stem
            version_path = self._run_dir / f"{stem}_v{state.cycle}.md"
            version_path.write_text(state.prd, encoding="utf-8")

    def _write_issue_registry(self, state: CycleState) -> None:
        with self._audit_trail.step(
            "write_issue_registry",
            artifact_root=self._output_dir,
            cycle=state.cycle,
        ):
            path = self._run_dir / "issue_registry.json"
            path.write_text(
                json.dumps([dataclasses.asdict(i) for i in state.issue_registry], indent=2),
                encoding="utf-8",
            )

    def _write_run_manifest(self, *, cycles: int, total_cost: float) -> None:
        manifest = {
            "topic": self._config.topic,
            "goal": self._config.goal,
            "primary_artifact": self._config.primary_artifact,
            "cycles": cycles,
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": [a.name for a in self._config.artifacts],
        }
        with self._audit_trail.step("write_run_manifest", artifact_root=self._output_dir, cycles=cycles):
            (self._run_dir / "run_manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

    def _handle_hitl_pause(self, state: CycleState) -> None:
        pending_path = self._run_dir / "pending_questions.json"
        guidance_path = self._output_dir / GUIDANCE_FILENAME
        write_pending_questions(state.pending_human_inputs, pending_path)
        (self._run_dir / _LAST_PAUSE_FILE).write_text(
            json.dumps({
                "cycle": state.cycle,
                "workflow": "refine",
                "target": "verifier",
                "gate_trigger": "after",
            }),
            encoding="utf-8",
        )
        packet = build_review_packet(
            workflow="refine",
            cycle=state.cycle,
            consecutive_clean_cycles=state.consecutive_clean_cycles,
            open_issues=state.issue_registry,
            pending_requests=state.pending_human_inputs,
        )
        write_review_packet(packet, self._output_dir / REVIEW_PACKET_FILENAME)
        print(
            f"\n[refine] {len(state.pending_human_inputs)} question(s) require human input.\n"
            f"Review packet:  {self._output_dir / REVIEW_PACKET_FILENAME}\n"
            f"Fill in answers in: {pending_path}\n"
            f"Optional: add steering guidance in: {guidance_path}\n"
            f"  (workflow=refine, target=verifier, gate_trigger=after, sequence={state.cycle})\n"
            f"Then re-run with --resume to continue.\n"
        )

    # ── Backend invocation ──────────────────────────────────────────────────

    def _invoke(self, prompt: str, backend: Backend, backend_name: str) -> AgentResponse:
        provider = getattr(backend, "provider_config", None)
        provider = provider if isinstance(provider, ProviderConfig) else None
        opts = build_call_options(self._config.execution, provider=provider)
        opts = apply_backend_capabilities(backend, opts)
        timeout = (
            provider.timeout_seconds
            if provider is not None and provider.timeout_seconds > 0
            else self._config.execution.timeout_seconds
        )
        resp = backend.invoke(prompt, opts, timeout=timeout)
        self._track_usage(resp, backend_name)
        return resp

    def _track_usage(self, resp: AgentResponse, backend_name: str) -> None:
        self._total_cost += resp.cost_usd
        self._total_input_tokens += resp.input_tokens
        self._total_output_tokens += resp.output_tokens

    def _track_cost(self, cost: float, backend_name: str) -> None:
        self._total_cost += cost
