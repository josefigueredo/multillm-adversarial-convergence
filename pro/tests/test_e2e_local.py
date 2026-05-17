"""End-to-end test: spin up the FastAPI app, connect a WS client,
broadcast a patch via /api/control, verify the WS sees the update.

Uses httpx + websockets against a locally-launched uvicorn in a thread.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time

import httpx
import pytest
import uvicorn
import websockets


@pytest.fixture(scope="module")
def server():
    import os

    os.environ["SLIDES_API_KEY"] = "test-e2e-key"
    from backend.local.server import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8770, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            httpx.get("http://127.0.0.1:8770/api/state", timeout=0.5)
            break
        except httpx.RequestError:
            time.sleep(0.1)
    else:
        raise RuntimeError("server failed to come up")

    yield "http://127.0.0.1:8770"
    srv.should_exit = True
    thread.join(timeout=3)


@pytest.mark.asyncio
async def test_websocket_receives_broadcast(server):
    base = server
    ws_url = base.replace("http", "ws") + "/ws"

    async with websockets.connect(ws_url) as ws:
        # Initial state arrives on connect
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert first["view"] == "deck"
        initial_version = first["version"]

        # POST a control patch
        async with httpx.AsyncClient() as http:
            r = await http.post(
                base + "/api/control",
                headers={"X-API-Key": "test-e2e-key"},
                json={"slide": 5, "view": "glossary", "glossary_term": "harness"},
            )
            assert r.status_code == 200

        # WS receives the broadcast
        broadcast = json.loads(await asyncio.wait_for(ws.recv(), timeout=2))
        assert broadcast["slide"] == 5
        assert broadcast["view"] == "glossary"
        assert broadcast["glossary_term"] == "harness"
        assert broadcast["version"] > initial_version
