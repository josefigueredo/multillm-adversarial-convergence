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
from .implement.document_refiner import DocumentRefiner
from .doctor import doctor_config_from_path, doctor_implement_config_from_path, doctor_output_text
from .explain import explain_config_text, explain_domain_packages, explain_implement_config_text, explain_resume_text
from .orchestrator import AutoResearcher
from .implement.plan_refiner import PlanRefiner
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

    # ── implement subcommand ─────────────────────────────────────────────────
    implement_p = subparsers.add_parser(
        "implement",
        help="Run an adversarial code-task implementation loop against a target repo.",
    )
    implement_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to an implement config YAML.",
    )
    implement_p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory for patches and artifacts. Defaults to output/<config-stem>/.",
    )
    implement_p.add_argument(
        "--resume",
        action="store_true",
        help="Resume from a previous paused implement run.",
    )
    implement_p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Validate config and target contract without running the implement loop.",
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
    explain_resume_p = explain_sub.add_parser(
        "resume",
        help="Explain the state of a paused or completed run.",
    )
    explain_resume_p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory of a previous run.",
    )

    explain_implement_p = explain_sub.add_parser(
        "implement",
        help="Print a human-readable explanation of an implement config YAML.",
    )
    explain_implement_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to an implement config YAML.",
    )

    explain_sub.add_parser(
        "domain-packages",
        help="Print the Research OS bounded-context package map.",
    )

    # ── doctor subcommand ────────────────────────────────────────────────────
    doctor_p = subparsers.add_parser(
        "doctor",
        help="Diagnose config or run health without executing anything.",
    )
    doctor_sub = doctor_p.add_subparsers(dest="doctor_subcommand", required=True)

    doctor_config_p = doctor_sub.add_parser(
        "config",
        help="Diagnose a research config YAML and report enforcement status.",
    )
    doctor_config_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a research config YAML.",
    )

    doctor_output_p = doctor_sub.add_parser(
        "output",
        help="Diagnose the health and completeness of a run output directory.",
    )
    doctor_output_p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output directory of a previous run.",
    )

    doctor_implement_p = doctor_sub.add_parser(
        "implement",
        help="Diagnose an implement config YAML and report safety boundary status.",
    )
    doctor_implement_p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to an implement config YAML.",
    )

    return parser


def _run_implement(args: argparse.Namespace, log: logging.Logger) -> int:
    from pathlib import Path as _Path

    from .implement.implement_loop import ImplementConfig
    from .implement.implement_runner import ImplementRunner
    from .provider_instances import instantiate_provider_backends

    config_path: _Path = args.config
    if not config_path.exists():
        log.error("Implement config file not found: %s", config_path)
        return 1

    try:
        impl_config = ImplementConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Invalid implement config: %s", exc)
        return 1

    output_dir: _Path = args.output or (_Path("output") / config_path.stem)
    target = impl_config.target

    if args.dry_run:
        roots_display = (
            ", ".join(str(r) for r in target.allowed_roots)
            if target.allowed_roots
            else "(all — no roots restricted)"
        )
        print(f"implement dry-run: config={config_path}, output={output_dir}")
        print(f"  target.path:            {target.path}")
        print(f"  target.execution_level: {target.execution_level}")
        print(f"  target.allowed_roots:   {roots_display}")
        return 0

    if impl_config.providers:
        backends = instantiate_provider_backends(impl_config.providers, impl_config.backends)
    else:
        all_names = impl_config.backends.all_backend_names()
        backends = get_backends(all_names)

    for name, be in backends.items():
        if not be.check_available():
            log.error(
                "%s CLI not found or not responding. "
                "Ensure '%s --version' works from the terminal.",
                name, be.cli_executable(),
            )
            return 1

    runner = ImplementRunner(
        config=impl_config,
        backends=backends,
        output_dir=output_dir,
        resume=args.resume,
    )
    return runner.run()


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


def _run_explain_resume(args: argparse.Namespace, log: logging.Logger) -> int:
    output_dir: Path = args.output
    if not output_dir.exists():
        log.error("Output directory not found: %s", output_dir)
        return 1

    print(explain_resume_text(output_dir))
    return 0


def _run_doctor_config(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    report = doctor_config_from_path(config_path)
    print(report.text)
    return report.exit_code


def _run_doctor_output(args: argparse.Namespace, log: logging.Logger) -> int:
    report = doctor_output_text(args.output)
    print(report.text)
    return report.exit_code


def _run_explain_implement(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    from .implement.implement_loop import ImplementConfig

    try:
        config = ImplementConfig.from_yaml(config_path)
    except (ValueError, OSError) as exc:
        log.error("Failed to load implement config: %s", exc)
        return 1

    print(explain_implement_config_text(config, config_path=config_path))
    return 0


def _run_doctor_implement(args: argparse.Namespace, log: logging.Logger) -> int:
    config_path: Path = args.config
    if not config_path.exists():
        log.error("Config file not found: %s", config_path)
        return 1

    report = doctor_implement_config_from_path(config_path)
    print(report.text)
    return report.exit_code


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
    if args.subcommand == "implement":
        return _run_implement(args, log)
    if args.subcommand == "explain":
        if args.explain_subcommand == "config":
            return _run_explain_config(args, log)
        if args.explain_subcommand == "resume":
            return _run_explain_resume(args, log)
        if args.explain_subcommand == "implement":
            return _run_explain_implement(args, log)
        if args.explain_subcommand == "domain-packages":
            print(explain_domain_packages())
            return 0
        log.error("explain subcommand %r is not yet implemented.", args.explain_subcommand)
        return 1

    if args.subcommand == "doctor":
        if args.doctor_subcommand == "config":
            return _run_doctor_config(args, log)
        if args.doctor_subcommand == "output":
            return _run_doctor_output(args, log)
        if args.doctor_subcommand == "implement":
            return _run_doctor_implement(args, log)
        log.error("doctor subcommand %r is not yet implemented.", args.doctor_subcommand)
        return 1

    log.error("Unknown subcommand: %s", args.subcommand)
    return 1


if __name__ == "__main__":
    sys.exit(main())
