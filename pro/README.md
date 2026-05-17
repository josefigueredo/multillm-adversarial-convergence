# pro — synchronized presentation backend

FastAPI local dev server + AWS Lambda production deployment for synchronized slide playback. Drives the static viewer pages in [`../docs/showcase-pro/`](../docs/showcase-pro/).

Adapted from [`slides-template-pro`](https://github.com/), retargeted at this repo's `docs/showcase-pro/` static tree.

## Quick start (local)

Prerequisite: [`uv`](https://docs.astral.sh/uv/) (installs Python 3.12+ on demand, manages the venv and lockfile).

```bash
make install                                    # one-time: uv sync --extra dev
SLIDES_API_KEY=$(openssl rand -hex 12) make dev # uv run uvicorn … on :8000
```

All Make targets shell out to `uv run` — no manual `source .venv/bin/activate` needed. The lockfile (`uv.lock`) is committed for reproducible installs.

Then:

- `http://localhost:8000/showcase/index.html` — landing
- `http://localhost:8000/showcase/deck/deck.html` — deck
- `http://localhost:8000/showcase/presenter/control.html` — presenter

`SLIDES_API_KEY` is required by the presenter; in local dev the FastAPI server inlines it into `/api/runtime-config` so the presenter picks it up automatically.

## What's served where

| Static path | URL | Source |
|---|---|---|
| `../docs/showcase-pro/` | `/showcase/...` | mounted with `html=True` (so `index.html` is the default) |
| WS plane | `/ws` | viewer subscribe |
| Control plane | `POST /api/control` | presenter push (requires `X-API-Key`) |
| State read | `GET /api/state` | debug snapshot |
| Bootstrap config | `GET /api/runtime-config` | inlines `apiKey` + `wsUrl` — **local only**, do not deploy |

## Layout

```
pro/
├── backend/
│   ├── shared/      ← BroadcastState · StateStore · Broadcaster · auth · apply_patch
│   ├── handlers/    ← AWS Lambda entrypoints (connect / disconnect / control)
│   └── local/       ← FastAPI dev server (server.py)
├── infrastructure/
│   ├── terraform/   ← AWS deployment + LocalStack profile
│   └── localstack/  ← docker-compose + bootstrap for offline e2e
├── tests/           ← state · auth · broadcaster · storage · WS e2e · LocalStack e2e
├── scripts/
├── Makefile         ← install · dev · test · tf-* · localstack-* · deploy-static
├── pyproject.toml   ← `slides-template-pro` package (isolated from this repo's root pyproject)
└── ARCHITECTURE.md  ← detailed design notes carried over from slides-template-pro
```

## Tests

```bash
make test       # unit + WS e2e + LocalStack e2e (skips e2e if prereqs missing)
make test-unit  # just unit tests
make test-e2e   # just e2e (requires LocalStack)
```

## Deploying to AWS

See `infrastructure/terraform/README.md`. TL;DR:

```bash
export SLIDES_API_KEY=$(openssl rand -hex 24)
make tf-init
make tf-apply
make deploy-static   # rsyncs ../docs/showcase-pro/ to the S3 bucket under /showcase/
```

Outputs include the WebSocket URL, control URL, and CloudFront URL. Bake them into the presenter page at deploy time (see ARCHITECTURE.md).

## Isolation from the framework

This Python project is **fully isolated** from the multi-LLM framework at the repo root:

- Its own `pyproject.toml` + `uv.lock` (`slides-template-pro` package)
- Its own `.venv` under `pro/.venv/` (managed by uv)
- Its own `Makefile` targets
- Its own `tests/` (doesn't share fixtures with `/tests/`)

The only coupling: the backend reads static files from `../docs/showcase-pro/`. That coupling is one line in `backend/local/server.py` (`STATIC_DIR`).
