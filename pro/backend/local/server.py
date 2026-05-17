"""FastAPI local dev server.

Daily-driver dev environment — speaks the same wire protocol the AWS
deployment does. Mounts the static showcase folder, exposes a WebSocket
endpoint for viewers, and a POST /control endpoint for the presenter.

Run with:
    uv run uvicorn backend.local.server:app --reload --port 8000
or:
    python -m backend.local.server
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.shared import (
    ApiKeyMismatch,
    BroadcastState,
    InMemoryBroadcaster,
    InMemoryStateStore,
    apply_patch,
    require_api_key,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC_DIR = REPO_ROOT / "docs" / "showcase-pro"


def _resolved_api_key() -> str:
    # If no key is provided, fall back to a random one so the server still
    # boots — but log it loudly so the developer notices.
    key = os.getenv("SLIDES_API_KEY")
    if not key:
        key = secrets.token_urlsafe(16)
        logger.warning(
            "SLIDES_API_KEY not set — generated ephemeral key for this run: %s", key
        )
    return key


API_KEY = _resolved_api_key()

store = InMemoryStateStore()
broadcaster = InMemoryBroadcaster()

app = FastAPI(title="slides-template-pro local")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/showcase/index.html")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "version": store.load().version}


@app.get("/api/state")
def get_state() -> dict:
    return store.load().model_dump()


@app.post("/api/control")
async def post_control(
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    try:
        require_api_key(x_api_key, API_KEY)
    except ApiKeyMismatch as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        patch = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")

    try:
        new_state = apply_patch(store.load(), patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.save(new_state)
    stale = await broadcaster.broadcast(new_state, store.list_connections())
    for cid in stale:
        broadcaster.unregister(cid)
        store.remove_connection(cid)
    return JSONResponse(new_state.model_dump())


@app.websocket("/ws")
async def ws_events(websocket: WebSocket) -> None:
    await websocket.accept()
    connection_id = secrets.token_urlsafe(12)
    broadcaster.register(connection_id, websocket)
    store.add_connection(connection_id)
    try:
        await websocket.send_text(store.load().model_dump_json())
        while True:
            # Viewers don't send anything; we just keep the connection alive
            # and react to disconnects. If a viewer ever speaks, we ignore.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unregister(connection_id)
        store.remove_connection(connection_id)


class _NoCacheStaticFiles(StaticFiles):
    """Dev-only StaticFiles that disables browser caching.

    Iterating on HTML/CSS/JS in this repo is much friendlier when the
    browser always re-fetches. Production (S3/CloudFront) sets its own
    cache headers; this only affects the local FastAPI server.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.mount("/showcase", _NoCacheStaticFiles(directory=str(STATIC_DIR), html=True), name="static")


@app.get("/api/runtime-config")
def runtime_config(request: Request) -> JSONResponse:
    """Tell the frontend where to connect.

    The API key is inlined here for local dev so you can drive the deck
    from the same browser without typing keys. The production deployment
    does NOT serve this endpoint — the presenter page reads the key from
    a URL parameter or prompt instead.
    """

    scheme = "wss" if request.url.scheme == "https" else "ws"
    host = request.headers.get("host", f"localhost:{os.getenv('PORT', '8000')}")
    return JSONResponse(
        {
            "wsUrl": f"{scheme}://{host}/ws",
            "controlUrl": "/api/control",
            "stateUrl": "/api/state",
            "apiKey": API_KEY,
            "mode": "local",
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.local.server:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
