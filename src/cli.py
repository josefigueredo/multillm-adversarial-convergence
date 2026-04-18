"""Entry point for the autoresearch-claude framework.

Parses CLI arguments, validates the config, checks for the selected
backend CLI, and launches the research loop, synthesis, or document refinement.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .backends import VALID_BACKENDS, get_backend, get_backends
from .config import VALID_STRATEGIES, DocumentConfig, ResearchConfig
from .document_refiner import DocumentRefiner
from .orchestrator import AutoResearcher
from .strategy import get_strategy


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        force=True,
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
    backend = get_backend(backend_name)
    strategy_name = args.strategy or config.execution.strategy
    output_dir: Path = (args.output or Path("output") / config_path.stem).resolve()

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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger("autoresearch")

    if args.subcommand == "run":
        return _run_research(args, log)
    if args.subcommand == "refine":
        return _run_refine(args, log)

    log.error("Unknown subcommand: %s", args.subcommand)
    return 1


if __name__ == "__main__":
    sys.exit(main())
