#!/usr/bin/env python3
"""Mock demo runner — replays a research run with minimal waits.

Reads source artifacts from ``output/localstack_alternatives_copilot_gemini/``
(iter_001..iter_006 plus knowledge_base, results, audit trail) and writes
them into ``output/demo/`` while streaming the framework's log format to
stdout. Synthesis artifacts come from ``docs/showcase/localstack-alternatives/raw/``
because the source run was OOM-killed before synthesis ever ran.

Pacing is tuned for a 60-90s screen recording that, sped up 2-3x, becomes
a crisp 25-40s demo. Edit the ``DELAY_*`` constants if you want a slower
or faster pace.

What this DOES NOT do:
- No backend calls, no Copilot/Gemini CLI invocations, no network
- No retries logged (the source run had three retry passes per iteration —
  hidden here for readability)
- No Spanish-language "new dimension" lines from the source iterations 3-4
  (cosmetic cleanup; the original Gemini adversary code-switched mid-run)

Usage:
    uv run python scripts/mock_demo.py
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "output" / "localstack_alternatives_copilot_gemini"
DEST = REPO / "output" / "demo"
SYNTHESIS_SRC = REPO / "docs" / "showcase" / "localstack-alternatives" / "raw"

# Pacing — short enough to film, long enough to read on playback.
DELAY_HEADER = 0.4
DELAY_RESEARCH = 2.5
DELAY_SCORE = 0.4
DELAY_NEW_DIM = 0.08
DELAY_KEEP = 0.3
DELAY_SYNTH_FILE = 0.18
DELAY_SYNTH_PHASE = 1.5

TOPIC = (
    "Compare alternatives to LocalStack for local AWS service emulation, "
    "given that LocalStack is moving to a fully paid/subscription model "
    "for commercial use. Evaluate nahuelnucera/ministack, hectorvent/floci, "
    "and any other viable open-source alternatives. Focus on practical "
    "usability for development and CI/CD pipelines."
)

# Curated iterations. Dimensions and scores match the real run.log;
# new-dimension lists are filtered to plausible research-shaped findings
# (the original adversary emitted many meta-critiques like "subjective
# claim" and several Spanish-language entries that read as noise).
ITERATIONS = [
    {
        "num": 1,
        "dimension": "Migration effort from LocalStack (config, SDK compatibility, breaking changes)",
        "scores": "Scores - coverage: 85.0, quality: 75.0, total: 79.0 (dim best: 0.0, global best: 0.0)",
        "new_dimensions": [
            "Floci's persistence bug fix status in versions after v1.4.0",
            "Floci's `/_localstack/health` endpoint compatibility",
            "Exact Docker volume mount path for MiniStack's `boot.d`/`ready.d` hooks",
            "fakecloud's init hook support",
            "Testcontainers ecosystem compatibility for all alternatives",
            "Viability of pinning to `localstack/localstack:3.8.1` as a bridge strategy",
            "Detailed service-level API operation coverage gaps beyond confirmed ones",
            "Floci's multi-account support documentation",
        ],
    },
    {
        "num": 2,
        "dimension": "CI/CD integration (GitHub Actions, GitLab CI, Jenkins)",
        "scores": "Scores - coverage: 58.8, quality: 75.0, total: 68.5 (dim best: 0.0, global best: 79.0)",
        "new_dimensions": [
            "CI/CD YAML examples not provided for each alternative",
            "Caching strategies for Docker image layers in CI runners",
            "Trade-offs for fakecloud init hook workarounds",
            "Floci's init hook system documentation depth",
            "MiniStack persistence layers incompletely identified",
            "MiniStack init hook volume mount path uncertain",
        ],
    },
    {
        "num": 3,
        "dimension": "Terraform / CDK / SAM / CloudFormation support",
        "scores": "Scores - coverage: 50.0, quality: 67.5, total: 60.5 (dim best: 0.0, global best: 79.0)",
        "new_dimensions": [
            "Verification of CloudFormation resource type counts per alternative",
            "Definition of `graceful fallback` and `hard-fails` for unsupported resources",
            "Terraform `TestAcc*` compatibility evidence for Floci and fakecloud",
            "AWS::CDK::Metadata no-op handling specifics",
            "Tool version pinning recommendations for reproducibility",
            "SAM CLI macro-transform support depth",
            "MiniStack project age and maturity timeline",
        ],
    },
    {
        "num": 4,
        "dimension": "AWS service coverage (S3, SQS, SNS, Lambda, DynamoDB, API Gateway, IAM, CloudFormation)",
        "scores": "Scores - coverage: 67.5, quality: 60.0, total: 63.0 (dim best: 0.0, global best: 79.0)",
        "new_dimensions": [
            "Per-service operation coverage matrices (LocalStack vs alternatives)",
            "DynamoDB `UpdateItem` `ReturnValues` compatibility (Floci issue #470)",
            "Lambda runtime versions supported by each alternative",
            "API Gateway HTTP API vs REST API support per alternative",
            "IAM policy evaluation engine fidelity",
        ],
    },
    {
        "num": 5,
        "dimension": "Community activity, maintenance status, and bus factor",
        "scores": "Scores - coverage: 50.0, quality: 57.5, total: 54.5 (dim best: 0.0, global best: 79.0)",
        "new_dimensions": [
            "Definition of `oldest project` baseline for community comparison",
            "Corporate backing or sponsorship evidence for each alternative",
            "Definition of `limited adoption runway` and quantitative criteria",
            "Release cadence metrics (releases per month, time-to-merge for PRs)",
        ],
    },
    {
        "num": 6,
        "dimension": "Licensing and pricing (LocalStack free vs Pro vs alternatives)",
        "scores": "Scores - coverage: 76.2, quality: 65.0, total: 69.5 (dim best: 0.0, global best: 79.0)",
        "new_dimensions": [
            "Direct legal evidence for LocalStack Hobby commercial-use restrictions",
            "AGPL-3.0 implications for `bundling` scenarios",
            "License audit for `fakecloud` SDK packages",
            "Persistence options for non-S3 services in MiniStack",
            "Multi-account support documentation status for Floci",
            "Documented init hook mechanisms for Floci and fakecloud",
            "Cloud Pods limit for LocalStack Hobby tier",
        ],
    },
]


def log(msg: str) -> None:
    """Print a log line in the framework's format and append to run.log."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts}  INFO      {msg}"
    print(line, flush=True)
    with (DEST / "run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def divider() -> None:
    log("=" * 60)


def copy_if_exists(src: Path, dst: Path) -> bool:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
        return True
    return False


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(
            f"Source run not found: {SOURCE}. The mock needs the real "
            f"localstack_alternatives_copilot_gemini run as its source of truth."
        )

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST / "iterations").mkdir()
    (DEST / "run.log").touch()

    log(
        "Starting autoresearch [adversarial (researcher: research_coder, "
        "adversary: adversary_reasoner, judge: adversary_reasoner)]: "
        f"{TOPIC}"
    )
    log(" (8 dimensions configured)")

    for fname in ("effective_config.json", "run_manifest.json", "methods.md", "rerun.sh"):
        copy_if_exists(SOURCE / fname, DEST / fname)
    time.sleep(DELAY_HEADER)

    for it in ITERATIONS:
        n = it["num"]
        divider()
        log(f"Iteration {n:03d}")
        divider()
        time.sleep(DELAY_HEADER)

        log(f"Dimension: {it['dimension']} (attempt 1/3)")
        time.sleep(DELAY_RESEARCH)

        log(it["scores"])
        time.sleep(DELAY_SCORE)

        for dim in it["new_dimensions"]:
            log(f"New dimension discovered: {dim}")
            time.sleep(DELAY_NEW_DIM)

        copy_if_exists(SOURCE / "iterations" / f"iter_{n:03d}.md",
                       DEST / "iterations" / f"iter_{n:03d}.md")
        for fname in ("knowledge_base.md", "results.tsv", "audit_trail.jsonl"):
            copy_if_exists(SOURCE / fname, DEST / fname)

        log("KEEP - merged into knowledge base.")
        time.sleep(DELAY_KEEP)

    divider()
    log("Generating synthesis from knowledge base...")
    time.sleep(DELAY_SYNTH_PHASE)

    if not SYNTHESIS_SRC.exists():
        log(f"Synthesis source not found: {SYNTHESIS_SRC} (skipping artifact copy)")
    else:
        synth_files = [
            "synthesis.md",
            "report.html",
            "dashboard.json",
            "metrics.json",
            "citations.json",
            "claims.json",
            "certainty_tables.json",
            "evidence_links.json",
            "evidence_quality.json",
            "search_log.json",
            "screening_log.json",
            "prompt_snapshot.json",
            "tool_trace.json",
            "contradictions.json",
        ]
        for fname in synth_files:
            if copy_if_exists(SYNTHESIS_SRC / fname, DEST / fname):
                log(f"Wrote {fname}")
                time.sleep(DELAY_SYNTH_FILE)

    log(f"Synthesis complete. Output directory: {DEST}")
    log("DONE")


if __name__ == "__main__":
    main()
