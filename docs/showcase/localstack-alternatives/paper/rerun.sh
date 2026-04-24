#!/usr/bin/env bash
set -euo pipefail

# Re-run this research job with the same config and output directory.
# Tip: override the output directory by editing the command below or copying it elsewhere.
autoresearch run --config /Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence/configs/localstack_alternatives_copilot_codex_paper.yaml --output /Users/josefigueredo/Code/josefigueredo/multillm-adversarial-convergence/output/localstack_alternatives_copilot_codex_paper "$@"
