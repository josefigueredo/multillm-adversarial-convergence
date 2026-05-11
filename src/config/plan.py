"""Plan-mode configuration (loaded by ``plan`` subcommand).

Independent of ``ResearchConfig`` and ``DocumentConfig``: plans go
through their own convergence loop with engineering-flavoured personas
(architect, tech_lead, qa_engineer, …) and a stricter default
convergence threshold than document mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .common import (
    BackendsConfig,
    ExecutionConfig,
    ProviderConfig,
    StrategyConfig,
    _parse_execution_config,
    _resolve_backends_and_providers,
)
from .document import (
    VALID_PERSONA_MODES,
    ArtifactConfig,
    SourceFileConfig,
    _parse_source_files,
)
from .hitl import HitlConfig, _parse_hitl_config


@dataclass(frozen=True)
class PlanPersonaConfig:
    """A single reviewer persona for the plan convergence loop.

    Attributes:
        name: Persona identifier — used for role-based source file filtering
            and as the default prompt file stem.
        prompt_file: Override prompt template filename.  Defaults to
            ``plan_persona_{name}.md`` when empty.
    """

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class PlanConfig:
    """Top-level configuration for a plan refinement run.

    Loaded from a YAML file with a top-level ``plan:`` key via :meth:`from_yaml`.
    Independent of ``ResearchConfig`` and ``DocumentConfig``.

    Attributes:
        topic: Short label for the plan being refined.
        goal: What the finished plan should enable — e.g. "unambiguous enough
            that a senior engineer can execute without clarifying questions."
        primary_artifact: Filename of the main document produced by Phase 1.
            Defaults to ``"PLAN.md"``.
        source_material: Path or raw text injected into the Builder prompt as
            seed content for cycle 0.
        convergence_cycles: Consecutive clean cycles required before stopping.
            Defaults to ``2`` (stricter than document mode's ``1``).
        max_cycles: Hard cap on total convergence cycles.  ``0`` means no cap.
        persona_mode: ``"parallel"`` runs all personas concurrently;
            ``"serial"`` runs them in declaration order.
        personas: Review personas executed each cycle.  Defaults to all seven
            plan-specific personas.
        artifacts: Phase 2 companion documents derived from the converged plan.
        source_files: Companion files injected as structured context into agent
            prompts, with per-file role targeting.  See :class:`SourceFileConfig`.
        backends: Role-to-backend mapping for the convergence loop.
        strategy_config: Strategy-level tuning (e.g. ``critique_depth``).
    """

    topic: str
    goal: str
    primary_artifact: str = "PLAN.md"
    source_material: str = ""
    convergence_cycles: int = 2
    max_cycles: int = 10
    persona_mode: str = "parallel"
    personas: tuple[PlanPersonaConfig, ...] = (
        PlanPersonaConfig("architect"),
        PlanPersonaConfig("tech_lead"),
        PlanPersonaConfig("qa_engineer"),
        PlanPersonaConfig("ai_engineer"),
        PlanPersonaConfig("data_engineer"),
        PlanPersonaConfig("security_engineer"),
        PlanPersonaConfig("devils_advocate"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    source_files: tuple[SourceFileConfig, ...] = ()
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    hitl: HitlConfig = field(default_factory=HitlConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "PlanConfig":
        """Load a plan config from a YAML file with a top-level ``plan:`` key.

        Expected YAML structure (all keys except ``topic`` are optional)::

            plan:
              topic: "Feature name"
              goal: "What the plan should enable"
              primary_artifact: "PLAN.md"
              source_material: ""
              convergence_cycles: 2
              max_cycles: 10
              persona_mode: parallel        # parallel | serial
              personas:
                - name: architect
                - name: tech_lead
              source_files:
                - path: docs/**/*.md
                  roles: [builder, architect]
              artifacts:
                - name: RISK_REGISTER.md
                  layer: companion
                  review: false
              backends:
                primary: claude
                research: [claude, gemini]
                judge: claude
                utility: gemini

        Args:
            path: Path to the YAML config file.  Relative ``source_files`` paths
                are resolved relative to this file's parent directory.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If the YAML is malformed, missing required fields, or a
                literal (non-glob) ``source_files`` path is not found on disk.
        """
        with open(path, encoding="utf-8") as f:
            try:
                raw: Any = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

        if not isinstance(raw, dict):
            raise ValueError(f"Config must be a YAML mapping, got {type(raw).__name__}")

        if "plan" not in raw:
            raise ValueError("Config must contain a top-level 'plan' key")

        plan_raw: dict[str, Any] = raw["plan"]

        if "topic" not in plan_raw:
            raise ValueError("'plan' section must contain a 'topic' field")

        persona_mode = plan_raw.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        raw_personas = plan_raw.get("personas", [])
        personas: tuple[PlanPersonaConfig, ...]
        if raw_personas:
            personas = tuple(
                PlanPersonaConfig(name=p["name"], prompt_file=p.get("prompt_file", ""))
                for p in raw_personas
            )
        else:
            personas = (
                PlanPersonaConfig("architect"),
                PlanPersonaConfig("tech_lead"),
                PlanPersonaConfig("qa_engineer"),
                PlanPersonaConfig("ai_engineer"),
                PlanPersonaConfig("data_engineer"),
                PlanPersonaConfig("security_engineer"),
                PlanPersonaConfig("devils_advocate"),
            )

        config_dir = path.parent
        persona_names = {p.name for p in personas}
        source_files = _parse_source_files(
            plan_raw.get("source_files", []), config_dir, persona_names
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in plan_raw.get("artifacts", [])
        )

        providers, backends_cfg = _resolve_backends_and_providers(plan_raw)

        strat_raw: dict[str, Any] = plan_raw.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )

        execution_cfg = _parse_execution_config(plan_raw.get("execution", {}))
        hitl_cfg = _parse_hitl_config(plan_raw.get("hitl", {}))

        return cls(
            topic=plan_raw["topic"],
            goal=plan_raw.get("goal", plan_raw["topic"]),
            primary_artifact=plan_raw.get("primary_artifact", "PLAN.md"),
            source_material=plan_raw.get("source_material", ""),
            convergence_cycles=plan_raw.get("convergence_cycles", 2),
            max_cycles=plan_raw.get("max_cycles", 10),
            persona_mode=persona_mode,
            personas=personas,
            artifacts=artifacts,
            source_files=source_files,
            providers=providers,
            backends=backends_cfg,
            strategy_config=strategy_cfg,
            execution=execution_cfg,
            hitl=hitl_cfg,
        )
