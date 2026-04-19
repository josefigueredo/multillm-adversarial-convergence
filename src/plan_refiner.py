"""PlanRefiner — plan convergence orchestrator.

Sibling to DocumentRefiner. Runs Phase 1 (plan convergence),
Phase 2 (artifact expansion), and Phase 3 (index generation).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .backends import AgentResponse, Backend, CallOptions
from .config import ArtifactConfig, PlanConfig
from .hitl import (
    append_human_decisions,
    load_human_decisions,
    write_pending_questions,
)
from .plan_loop import (
    PlanCycleContext,
    PlanCycleState,
    _plan_should_stop,
    run_plan_cycle,
)
from .plan_strategy import PlanStrategy
from .prompts import render

log = logging.getLogger("autoresearch")

EXIT_HUMAN_REQUIRED = 2


class PlanRefiner:
    """Orchestrates a plan convergence run (plan subcommand).

    Phase 1 — Convergence: Plan refined through adversarial cycles until clean.
    Phase 2 — Expansion: Companion artifacts generated from the converged plan.
    Phase 3 — Indexing: DOCS_INDEX.md and README.md auto-generated.
    """

    def __init__(
        self,
        config: PlanConfig,
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

    # ── Public entry point ──────────────────────────────────────────────────

    def run(self, *, interactive: bool = True) -> int:
        """Run all three phases. Returns exit code (0 on success, 2 on HITL pause)."""
        self._setup_dirs()

        strategy = PlanStrategy(self._config, self._backends)
        state = self._init_state()

        ctx = PlanCycleContext(
            call_with=self._invoke,
            invoke_for_strategy=self._invoke,
            track_usage=self._track_usage,
            track_cost=self._track_cost,
            config=self._config,
            human_decisions=state.human_decisions,
            update_issue_registry=lambda issues: None,
        )

        # Phase 1 — Convergence
        while not _plan_should_stop(state, self._config):
            valid_count, stale_count, deferred_count = run_plan_cycle(
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
                return EXIT_HUMAN_REQUIRED

        # Write converged primary artifact
        self._write_primary_artifact(state.plan)
        log.info(
            "[plan] Phase 1 complete — %s converged in %d cycle(s).",
            self._config.primary_artifact, state.cycle,
        )

        # Phase 2 — Expansion
        self._run_phase2(state.plan, strategy, ctx)

        # Phase 3 — Indexing
        self._run_phase3()

        # Finalize
        self._write_run_manifest(cycles=state.cycle, total_cost=self._total_cost)
        log.info("[plan] Done. Output at: %s", self._output_dir)
        return 0

    # ── Phase 2: Expansion ──────────────────────────────────────────────────

    def _run_phase2(self, plan: str, strategy: PlanStrategy, ctx: PlanCycleContext) -> None:
        for artifact in self._config.artifacts:
            log.info("[phase2] Generating %s ...", artifact.name)
            content = self._generate_artifact(plan, artifact, strategy, ctx)
            out_path = self._output_dir / artifact.name
            out_path.write_text(content, encoding="utf-8")
            log.info("[phase2] Wrote %s", artifact.name)

    def _generate_artifact(
        self,
        plan: str,
        artifact: ArtifactConfig,
        strategy: PlanStrategy,
        ctx: PlanCycleContext,
    ) -> str:
        stem = Path(artifact.name).stem
        prompt_file = artifact.prompt_file or f"artifact_{stem}.md"
        try:
            prompt = render(prompt_file, plan=plan, topic=self._config.topic,
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

    def _init_state(self) -> PlanCycleState:
        state = PlanCycleState(plan_path=Path(self._config.primary_artifact))
        if self._resume:
            decisions_path = self._run_dir / "human_decisions.json"
            state.human_decisions = load_human_decisions(decisions_path)
        return state

    def _setup_dirs(self) -> None:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "cycles").mkdir(exist_ok=True)

    def _write_primary_artifact(self, content: str) -> None:
        (self._output_dir / self._config.primary_artifact).write_text(
            content, encoding="utf-8"
        )

    def _write_cycle_snapshot(self, state: PlanCycleState) -> None:
        snap = self._run_dir / "cycles" / f"cycle_{state.cycle:03d}.md"
        snap.write_text(
            f"# Cycle {state.cycle}\n\n"
            f"Valid issues: {sum(1 for i in state.issue_registry if i.status == 'valid')}\n"
            f"Clean streak: {state.consecutive_clean_cycles}\n\n"
            f"## Plan snapshot\n\n{state.plan[:2000]}\n",
            encoding="utf-8",
        )
        stem = Path(self._config.primary_artifact).stem
        version_path = self._run_dir / f"{stem}_v{state.cycle}.md"
        version_path.write_text(state.plan, encoding="utf-8")

    def _write_issue_registry(self, state: PlanCycleState) -> None:
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
        (self._run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def _handle_hitl_pause(self, state: PlanCycleState) -> None:
        pending_path = self._run_dir / "pending_questions.json"
        write_pending_questions(state.pending_human_inputs, pending_path)
        print(
            f"\n[plan] {len(state.pending_human_inputs)} question(s) require human input.\n"
            f"Fill in answers in: {pending_path}\n"
            f"Then re-run with --resume to continue.\n"
        )

    # ── Backend invocation ──────────────────────────────────────────────────

    def _invoke(self, prompt: str, backend: Backend, backend_name: str) -> AgentResponse:
        opts = CallOptions(
            max_turns=self._config.execution.max_turns,
            allowed_tools=self._config.execution.allowed_tools,
        )
        resp = backend.invoke(prompt, opts, timeout=self._config.execution.timeout_seconds)
        self._track_usage(resp, backend_name)
        return resp

    def _track_usage(self, resp: AgentResponse, backend_name: str) -> None:
        self._total_cost += resp.cost_usd
        self._total_input_tokens += resp.input_tokens
        self._total_output_tokens += resp.output_tokens

    def _track_cost(self, cost: float, backend_name: str) -> None:
        self._total_cost += cost
