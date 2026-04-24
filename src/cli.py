"""Entry point for the autoresearch-claude framework.

Parses CLI arguments, validates the config, checks for the selected
backend CLI, and launches the research loop, synthesis, document refinement, or plan refinement.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .backends import VALID_BACKENDS, get_backend, get_backends
from .config import VALID_STRATEGIES, BackendsConfig, DocumentConfig, PlanConfig, ResearchConfig
from .dry_run import build_convergence_dry_run_summary, build_dry_run_summary, render_dry_run_summary
from .document_refiner import DocumentRefiner
from .explain import explain_config_text
from .orchestrator import AutoResearcher
from .plan_refiner import PlanRefiner
from .provider_instances import instantiate_provider_backends
from .strategy import get_strategy


def _setup_logging(verbose: bool, *, log_path: Path | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
        handlers=handlers,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoresearch",
        description="Autonomous research loop powered by AI coding agent CLIs.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # ── run subcommand ───────────────────────────────────────────────────────
    run_p = subparsers.add_parser("run", help="Run the autonomous research loop.")
    run_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a research config YAML (see configs/_template.yaml).",
    )
    run_p.add_argument(
        "--backend",
        choices=VALID_BACKENDS,
        default=None,
        help="CLI backend to use. Overrides the config file.",
    )
    run_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/<config-stem>/.",
    )
    run_p.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing iteration files in the output directory.",
    )
    run_p.add_argument(
        "--synthesize",
        action="store_true",
        help="Generate a synthesis report from existing data and exit.",
    )
    run_p.add_argument(
        "--strategy",
        choices=VALID_STRATEGIES,
        default=None,
        help="Multi-backend strategy. Overrides the config file.",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config, backend wiring, and planned outputs without running the research loop.",
    )

    # ── refine subcommand ────────────────────────────────────────────────────
    refine_p = subparsers.add_parser(
        "refine",
        help="Refine a document through adversarial convergence cycles.",
    )
    refine_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a document config YAML.",
    )
    refine_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/<config-stem>/.",
    )
    refine_p.add_argument(
        "--resume",
        action="store_true",
        help="Load existing human decisions and continue a paused run.",
    )
    refine_p.add_argument(
        "--no-interactive",
        dest="no_interactive",
        action="store_true",
        help="Disable interactive HITL prompts. Exit with code 2 when human input is needed.",
    )
    refine_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config, backend wiring, and planned outputs without running refinement.",
    )

    # ── plan subcommand ──────────────────────────────────────────────────────
    plan_p = subparsers.add_parser(
        "plan",
        help="Refine an implementation plan through adversarial convergence cycles.",
    )
    plan_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a plan config YAML (see configs/plan_template.yaml).",
    )
    plan_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory. Defaults to output/<config-stem>/.",
    )
    plan_p.add_argument(
        "--resume",
        action="store_true",
        help="Load existing human decisions and continue a paused run.",
    )
    plan_p.add_argument(
        "--no-interactive",
        dest="no_interactive",
        action="store_true",
        help="Disable interactive HITL prompts. Exit with code 2 when human input is needed.",
    )
    plan_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config, backend wiring, and planned outputs without running plan refinement.",
    )

    # ── explain subcommand ───────────────────────────────────────────────────
    explain_p = subparsers.add_parser(
        "explain",
        help="Explain run configuration or saved run state without executing anything.",
    )
    explain_sub = explain_p.add_subparsers(dest="explain_subcommand", required=True)

    explain_config_p = explain_sub.add_parser(
        "config",
        help="Print a human-readable explanation of a research config YAML.",
    )
    explain_config_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a research config YAML.",
    )

    # explain resume is reserved for Step 4
    explain_sub.add_parser(
        "resume",
        help="Explain the state of a paused run (Step 4).",
    )

    return parser


def _run_research(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = ResearchConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load config: %s", exc)
        return 1

    backend_name = args.backend or config.execution.backend
    strategy_name = args.strategy or config.execution.strategy
    output_dir: Path = (args.output or Path("output") / config_path.stem).resolve()

    if args.dry_run and args.resume:
        log.error("--dry-run cannot be combined with --resume.")
        return 1
    if args.dry_run and args.synthesize:
        log.error("--dry-run cannot be combined with --synthesize.")
        return 1

    if not args.resume and not args.synthesize and output_dir.exists():
        iters_dir = output_dir / "iterations"
        if iters_dir.exists():
            existing = list(iters_dir.glob("iter_*.md"))
            if existing:
                log.info(
                    "Found %d existing iterations in %s. "
                    "Use --resume to continue, or they will be preserved alongside new data.",
                    len(existing), output_dir,
                )

    if config.providers:
        role_config = config.execution.backends
        if strategy_name == "single":
            role_config = BackendsConfig(
                primary=config.execution.backends.primary,
                research=(config.execution.backends.primary,),
                judge=config.execution.backends.judge,
                utility=config.execution.backends.utility,
            )
        backends = instantiate_provider_backends(config.providers, role_config)
        backend = backends[config.execution.backends.primary]
    else:
        backend = get_backend(backend_name)
        all_names = config.execution.backends.all_backend_names()
        if strategy_name == "single":
            all_names = {backend_name}
        backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    strategy = get_strategy(
        strategy_name,
        config.execution.backends,
        config.execution.strategy_config,
        backends,
    )

    if args.dry_run:
        summary = build_dry_run_summary(
            config=config,
            config_path=config_path,
            output_dir=output_dir,
            backends=backends,
        )
        log.info("%s", render_dry_run_summary(summary))
        return 0

    _setup_logging(args.verbose, log_path=output_dir / "run.log")
    log = logging.getLogger("autoresearch")

    researcher = AutoResearcher(
        config=config,
        backend=backend,
        output_dir=output_dir,
        backends=backends,
        strategy=strategy,
        resume=args.resume,
        config_path=config_path,
    )

    try:
        if args.synthesize:
            researcher.synthesize_only()
        else:
            researcher.run()
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1

    return 0


def _run_refine(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = DocumentConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load document config: %s", exc)
        return 1

    output_dir: Path = (args.output or Path("output") / config_path.stem).resolve()

    if args.dry_run and args.resume:
        log.error("--dry-run cannot be combined with --resume.")
        return 1

    if config.providers:
        backends = instantiate_provider_backends(config.providers, config.backends)
    else:
        all_names = config.backends.all_backend_names()
        backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    if args.dry_run:
        summary = build_convergence_dry_run_summary(
            mode="refine",
            config=config,
            config_path=config_path,
            output_dir=output_dir,
            backends=backends,
        )
        log.info("%s", render_dry_run_summary(summary))
        return 0

    _setup_logging(args.verbose, log_path=output_dir / "run.log")
    log = logging.getLogger("autoresearch")

    refiner = DocumentRefiner(
        config=config,
        output_dir=output_dir,
        backends=backends,
        resume=args.resume,
    )

    try:
        return refiner.run(interactive=not args.no_interactive)
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1


def _run_plan(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = PlanConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load plan config: %s", exc)
        return 1

    output_dir: Path = (args.output or Path("output") / config_path.stem).resolve()

    if args.dry_run and args.resume:
        log.error("--dry-run cannot be combined with --resume.")
        return 1

    if config.providers:
        backends = instantiate_provider_backends(config.providers, config.backends)
    else:
        all_names = config.backends.all_backend_names()
        backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    if args.dry_run:
        summary = build_convergence_dry_run_summary(
            mode="plan",
            config=config,
            config_path=config_path,
            output_dir=output_dir,
            backends=backends,
        )
        log.info("%s", render_dry_run_summary(summary))
        return 0

    _setup_logging(args.verbose, log_path=output_dir / "run.log")
    log = logging.getLogger("autoresearch")

    refiner = PlanRefiner(
        config=config,
        output_dir=output_dir,
        backends=backends,
        resume=args.resume,
    )

    try:
        return refiner.run(interactive=not args.no_interactive)
    except Exception as exc:
        log.error("Unexpected error: %s", exc, exc_info=args.verbose)
        return 1


def _run_explain_config(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    try:
        config = ResearchConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load config: %s", exc)
        return 1

    print(explain_config_text(config, config_path=config_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("autoresearch")

    if args.subcommand == "run":
        return _run_research(args, log)
    if args.subcommand == "refine":
        return _run_refine(args, log)
    if args.subcommand == "plan":
        return _run_plan(args, log)
    if args.subcommand == "explain":
        if args.explain_subcommand == "config":
            return _run_explain_config(args, log)
        log.error("explain subcommand %r is not yet implemented.", args.explain_subcommand)
        return 1

    log.error("Unknown subcommand: %s", args.subcommand)
    return 1


if __name__ == "__main__":
    sys.exit(main())
