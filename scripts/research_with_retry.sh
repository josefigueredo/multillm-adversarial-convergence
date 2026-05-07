#!/usr/bin/env bash
# Run a research config with auto-retry-and-resume on transient failures.
#
# What this handles:
#   - OOM kill (exit 137) — kernel SIGKILL'd the process
#   - SIGTERM (exit 143) — supervisor signalled stop
#   - SIGSEGV (exit 139) — process crashed
#   - any non-zero exit OTHER than 130 (Ctrl+C, user-requested stop)
#
# What this does NOT handle:
#   - a Ctrl+C (exit 130) — treated as user intent, no retry
#   - configuration errors (exit 2) — fail-fast, fix the config
#
# After the first failure, all subsequent attempts add ``--resume`` so the
# orchestrator picks up from the last completed iteration rather than
# starting fresh.  The framework already handles rate-limit backoff
# internally (see Architecture diagram in docs/research.md); this wrapper
# is for hard kills and quota exhaustion that survive the internal retry.
#
# Backoff: 60s, 120s, 240s, 480s, 960s, then capped at 1800s (30 min).
# Cap on attempts: 10.
#
# Usage:
#   ./scripts/research_with_retry.sh configs/research/<name>.yaml
#   ./scripts/research_with_retry.sh configs/research/<name>.yaml --max-attempts 5
#   ./scripts/research_with_retry.sh configs/research/<name>.yaml --backoff 120

set -uo pipefail

CONFIG=""
MAX_ATTEMPTS=10
BACKOFF=60
BACKOFF_CAP=1800

while [ $# -gt 0 ]; do
  case "$1" in
    --max-attempts) MAX_ATTEMPTS="$2"; shift 2 ;;
    --backoff)      BACKOFF="$2";      shift 2 ;;
    -h|--help)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*)
      echo "ERROR: unknown flag: $1" >&2
      exit 2 ;;
    *)
      if [ -z "$CONFIG" ]; then CONFIG="$1"; else echo "ERROR: unexpected arg: $1" >&2; exit 2; fi
      shift ;;
  esac
done

if [ -z "$CONFIG" ]; then
  echo "ERROR: config path required" >&2
  echo "usage: $0 <config-path> [--max-attempts N] [--backoff SECONDS]" >&2
  exit 2
fi

if [ ! -f "$CONFIG" ]; then
  echo "ERROR: config file not found: $CONFIG" >&2
  exit 2
fi

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
RUN_NAME=$(basename "$CONFIG" .yaml)
LOG_FILE="$LOG_DIR/${RUN_NAME}-$(date +%Y%m%d-%H%M%S).log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_FILE"; }

attempt=0
backoff="$BACKOFF"
extra_flags=""

trap 'log "interrupted by user — exiting"; exit 130' INT TERM

log "config:        $CONFIG"
log "log file:      $LOG_FILE"
log "max attempts:  $MAX_ATTEMPTS"
log "initial backoff: ${BACKOFF}s (cap ${BACKOFF_CAP}s, doubled per failure)"
log ""

while true; do
  attempt=$((attempt + 1))
  log "=== attempt $attempt / $MAX_ATTEMPTS ==="
  log "running: uv run python -m src.cli research --config $CONFIG $extra_flags"
  set +e
  uv run python -m src.cli research --config "$CONFIG" $extra_flags 2>&1 | tee -a "$LOG_FILE"
  rc=${PIPESTATUS[0]}
  set -e

  case "$rc" in
    0)
      log ""
      log "✓ run finished cleanly on attempt $attempt"
      log "log: $LOG_FILE"
      exit 0 ;;
    130)
      log ""
      log "✗ user interrupt (exit 130) — not retrying"
      exit 130 ;;
    2)
      log ""
      log "✗ configuration error (exit 2) — not retrying; fix config and re-run"
      exit 2 ;;
    *)
      log ""
      log "✗ failed with exit $rc"
      ;;
  esac

  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    log ""
    log "✗ giving up after $attempt attempts (last exit: $rc)"
    log "log: $LOG_FILE"
    exit 1
  fi

  log "sleeping ${backoff}s before next attempt (attempt $((attempt + 1)) will use --resume)"
  sleep "$backoff"

  # Exponential backoff, capped
  backoff=$((backoff * 2))
  if [ "$backoff" -gt "$BACKOFF_CAP" ]; then backoff="$BACKOFF_CAP"; fi

  # All subsequent attempts resume from existing iteration files
  extra_flags="--resume"
done
