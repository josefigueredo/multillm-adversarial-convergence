"""Manual one-shot test of `_compress_knowledge_base` against an existing run.

Skips the iteration loop entirely so you can verify the compress path
without burning paid LLM calls. Builds the same context the loop would
build, points it at a TEMP kb_path so the live state isn't overwritten,
and prints word counts before/after.

Usage:
    uv run python scripts/test_compress.py <config.yaml>

Optional env: RESEARCH_COMPRESS_MIN_FREE_GB=<float>
"""
from __future__ import annotations

import sys
from pathlib import Path

# When invoked as ``python scripts/test_compress.py`` the repo root isn't on
# sys.path. Insert it so ``from src...`` resolves the same way ``-m src.cli``
# does. Sibling scripts assume the user runs via ``-m``; here we want both.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ResearchConfig
from src.orchestrator import AutoResearcher
from src.provider_instances import instantiate_provider_backends
from src.backends import get_backend, get_backends
from src.strategy import get_strategy
from src.research_loop import _compress_knowledge_base


def main(config_arg: str) -> int:
    config_path = Path(config_arg).resolve()
    config = ResearchConfig.from_yaml(config_path)
    output_dir = (Path("output") / config_path.stem).resolve()
    kb_path = output_dir / "knowledge_base.md"
    if not kb_path.exists():
        print(f"ERROR: {kb_path} not found — run the loop at least once first.", file=sys.stderr)
        return 2

    if config.providers:
        backends = instantiate_provider_backends(config.providers, config.execution.backends)
        backend = backends[config.execution.backends.primary]
    else:
        backend = get_backend(config.execution.backend)
        backends = get_backends(config.execution.backends.all_backend_names())

    strategy = get_strategy(
        config.execution.strategy,
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
        resume=True,
        config_path=config_path,
    )

    # Load resume state into the orchestrator (knowledge_base, iteration, ...)
    researcher._resume()  # noqa: SLF001 — debug script

    ctx = researcher._build_loop_context()  # noqa: SLF001
    state = researcher._build_loop_state()  # noqa: SLF001

    # Redirect writes to a sandbox path so the live KB isn't overwritten
    # if compress succeeds — user can diff and decide whether to promote.
    sandbox_kb = output_dir / "knowledge_base.compressed.md"
    state.kb_path = sandbox_kb

    before = len(state.knowledge_base.split())
    print(f"[test_compress] backend = {ctx.strategy.get_compress_backend().name}")
    print(f"[test_compress] before = {before} words")
    print(f"[test_compress] target = {state.KB_MAX_WORDS} words")
    print(f"[test_compress] writing to: {sandbox_kb}")
    print()

    _compress_knowledge_base(ctx, state)

    after = len(state.knowledge_base.split())
    print()
    print(f"[test_compress] after  = {after} words")
    if sandbox_kb.exists():
        print(f"[test_compress] artifact saved at {sandbox_kb}")
        print(f"[test_compress] to promote: mv {sandbox_kb} {kb_path}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
