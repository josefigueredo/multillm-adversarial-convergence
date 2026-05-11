"""Document-mode configuration (loaded by ``refine`` subcommand).

Independent of ``ResearchConfig``: documents are PRDs / architecture
notes that converge through a Builder/Challenger persona loop, not
through a research-iteration loop.
"""

from __future__ import annotations

import logging
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
from .hitl import HitlConfig, _parse_hitl_config

log = logging.getLogger("autoresearch")

VALID_PERSONA_MODES = ("parallel", "serial")


@dataclass(frozen=True)
class PersonaConfig:
    """A single reviewer persona for the document convergence loop."""

    name: str
    prompt_file: str = ""


@dataclass(frozen=True)
class ArtifactConfig:
    """A secondary artifact generated in Phase 2 (Expansion)."""

    name: str
    layer: str
    prompt_file: str = ""
    review: bool = True


@dataclass(frozen=True)
class SourceFileConfig:
    """A single source file injected into agent prompts during document convergence.

    Each instance represents one resolved file (glob patterns are already expanded
    by ``_parse_source_files`` before construction).

    Attributes:
        path: Absolute path to the file on disk.  Always a single concrete file —
            never a glob pattern or directory.
        roles: Agent roles that receive this file's content.  Valid values are
            ``"builder"``, ``"challenger"``, any persona name declared in the config,
            or the sentinel ``"all"`` (expanded to all concrete roles at load time).
    """

    path: str
    roles: tuple[str, ...]


def _parse_source_files(
    raw_entries: list[dict[str, Any]],
    config_dir: Path,
    persona_names: set[str],
) -> tuple[SourceFileConfig, ...]:
    """Resolve ``source_files`` YAML entries into one ``SourceFileConfig`` per matched file.

    Path resolution rules (in priority order):

    1. **Glob** (pattern contains ``*``, ``?``, or ``[``):
       - Absolute glob (starts with ``/``): expanded via ``Path('/').glob(relative_pattern)``
         so that ``**`` traversal works correctly.
       - Relative glob: expanded relative to ``config_dir``.
       - A glob that matches nothing logs a warning and is silently skipped.

    2. **Absolute literal** (starts with ``/``, no glob chars):
       Validated with ``Path.exists()``; raises ``ValueError`` if missing.

    3. **Relative literal**:
       Resolved as ``config_dir / pattern``; raises ``ValueError`` if missing.

    Role expansion:
       ``"all"`` expands to ``{"builder", "challenger"} | persona_names``.
       Unknown role names are stored as-is and silently accepted (they will simply
       never match an agent call, which is harmless).

    Args:
        raw_entries: Parsed YAML list of ``{path: ..., roles: [...]}`` dicts.
        config_dir: Directory containing the config file; used to resolve relative paths.
        persona_names: Concrete persona names declared in the config (used to expand ``"all"``).

    Returns:
        A tuple of ``SourceFileConfig`` instances, one per matched file.

    Raises:
        ValueError: If a literal (non-glob) path does not exist on disk.
    """
    all_roles = {"builder", "challenger"} | persona_names
    result: list[SourceFileConfig] = []

    for entry in raw_entries:
        pattern: str = entry["path"]
        raw_roles: list[str] = entry.get("roles", ["builder"])

        roles: set[str] = set()
        for r in raw_roles:
            if r == "all":
                roles |= all_roles
            else:
                roles.add(r)
        roles_tuple = tuple(sorted(roles))

        is_absolute = Path(pattern).is_absolute()
        has_glob = any(c in pattern for c in "*?[")

        if has_glob:
            if is_absolute:
                p = Path(pattern)
                matched = sorted(Path('/').glob(str(p.relative_to('/'))))
            else:
                matched = sorted(config_dir.glob(pattern))
            if not matched:
                log.warning("source_files glob '%s' matched no files — skipping", pattern)
            for m in matched:
                result.append(SourceFileConfig(path=str(m), roles=roles_tuple))
        elif is_absolute:
            p = Path(pattern)
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))
        else:
            p = config_dir / pattern
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))

    return tuple(result)


@dataclass(frozen=True)
class DocumentConfig:
    """Top-level configuration for a document refinement run.

    Loaded from a YAML file with a top-level ``document:`` key via
    :meth:`from_yaml`.  Independent of ``ResearchConfig``.

    Attributes:
        topic: Short label for the document being refined (e.g. ``"Iris Platform"``).
        goal: One-paragraph description of what the finished document should achieve
            and who will consume it.
        primary_artifact: Filename of the main document produced by Phase 1
            (convergence).  Defaults to ``"PRD.md"``.
        source_material: Path or raw text injected into the Builder prompt as seed
            content for cycle 0.  Kept for backward compatibility alongside
            ``source_files``.
        convergence_cycles: Number of consecutive clean cycles (no accepted critiques)
            required before Phase 1 stops.
        max_cycles: Hard cap on total convergence cycles.  ``0`` means no cap.
        persona_mode: ``"parallel"`` runs all persona reviewers concurrently;
            ``"serial"`` runs them in declaration order.
        personas: Review personas executed each cycle.  Defaults to
            ``architect``, ``scrum_master``, and ``product_owner``.
        artifacts: Phase 2 companion documents derived from the converged PRD.
        source_files: Companion files injected as structured context into agent
            prompts.  Each entry targets specific roles (``builder``, ``challenger``,
            persona names, or ``"all"``).  See :class:`SourceFileConfig`.
        backends: Role-to-backend mapping for the convergence loop.
        strategy_config: Strategy-level tuning (e.g. ``critique_depth``).
    """

    topic: str
    goal: str
    primary_artifact: str = "PRD.md"
    source_material: str = ""
    convergence_cycles: int = 1
    max_cycles: int = 0
    persona_mode: str = "parallel"
    personas: tuple[PersonaConfig, ...] = (
        PersonaConfig("architect"),
        PersonaConfig("scrum_master"),
        PersonaConfig("product_owner"),
    )
    artifacts: tuple[ArtifactConfig, ...] = ()
    source_files: tuple[SourceFileConfig, ...] = ()
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    backends: BackendsConfig = field(default_factory=BackendsConfig)
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    hitl: HitlConfig = field(default_factory=HitlConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "DocumentConfig":
        """Load a document config from a YAML file with a top-level ``document:`` key.

        Expected YAML structure (all keys except ``topic`` are optional)::

            document:
              topic: "Feature name"
              goal: "What the PRD should achieve"
              primary_artifact: "PRD.md"
              source_material: ""          # path or raw text for Builder seed
              convergence_cycles: 2
              max_cycles: 10
              persona_mode: parallel        # parallel | serial
              personas:
                - name: architect
                - name: scrum_master
                - name: product_owner
              source_files:
                - path: docs/**/*.md       # glob, absolute, or relative
                  roles: [builder, architect]
                - path: /abs/path/file.md
                  roles: [all]
              artifacts:
                - name: ARCHITECTURE.md
                  layer: execution
                  review: true
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

        if "document" not in raw:
            raise ValueError("Config must contain a top-level 'document' key")

        doc: dict[str, Any] = raw["document"]

        if "topic" not in doc:
            raise ValueError("'document' section must contain a 'topic' field")

        persona_mode = doc.get("persona_mode", "parallel")
        if persona_mode not in VALID_PERSONA_MODES:
            raise ValueError(
                f"Invalid persona_mode '{persona_mode}'. Must be one of: {', '.join(VALID_PERSONA_MODES)}"
            )

        raw_personas = doc.get("personas", [])
        personas = tuple(
            PersonaConfig(name=p["name"], prompt_file=p.get("prompt_file", ""))
            for p in raw_personas
        ) if raw_personas else (
            PersonaConfig("architect"),
            PersonaConfig("scrum_master"),
            PersonaConfig("product_owner"),
        )

        config_dir = path.parent
        persona_names = {p.name for p in personas}
        source_files = _parse_source_files(
            doc.get("source_files", []), config_dir, persona_names
        )

        artifacts = tuple(
            ArtifactConfig(
                name=a["name"],
                layer=a["layer"],
                prompt_file=a.get("prompt_file", ""),
                review=a.get("review", True),
            )
            for a in doc.get("artifacts", [])
        )

        providers, backends_cfg = _resolve_backends_and_providers(doc)

        strat_raw: dict[str, Any] = doc.get("strategy_config", {})
        strategy_cfg = StrategyConfig(
            critique_depth=strat_raw.get("critique_depth", "standard"),
        )
        execution_cfg = _parse_execution_config(doc.get("execution", {}))
        hitl_cfg = _parse_hitl_config(doc.get("hitl", {}))

        return cls(
            topic=doc["topic"],
            goal=doc.get("goal", doc["topic"]),
            primary_artifact=doc.get("primary_artifact", "PRD.md"),
            source_material=doc.get("source_material", ""),
            convergence_cycles=doc.get("convergence_cycles", 1),
            max_cycles=doc.get("max_cycles", 0),
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
