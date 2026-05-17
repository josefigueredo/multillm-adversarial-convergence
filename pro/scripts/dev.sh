#!/usr/bin/env bash
# Convenience runner: load .env then start the FastAPI server with reload.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a; source .env; set +a
fi

if [ ! -d .venv ]; then
  echo "→ creating venv"
  python3.12 -m venv .venv
  .venv/bin/pip install -e ".[dev]" >/dev/null
fi

exec .venv/bin/uvicorn backend.local.server:app --reload --port "${PORT:-8000}"
