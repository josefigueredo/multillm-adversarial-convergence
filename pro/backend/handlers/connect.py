"""WebSocket $connect handler.

API Gateway hits this when a viewer opens the WebSocket. We register the
connection id so the broadcast loop can send to it later, then push the
current state immediately so the viewer doesn't see a blank deck.

The initial-state push is best-effort: if it fails (network glitch,
client already gone, misconfigured endpoint in a test environment), the
connection is still registered and the next /control patch will reach it.
"""

from __future__ import annotations

import asyncio
import logging

from handlers._aws import broadcaster, state_store

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, _context):
    connection_id = event["requestContext"]["connectionId"]
    store = state_store()
    store.add_connection(connection_id)

    try:
        asyncio.run(broadcaster().send_to(connection_id, store.load()))
    except Exception as exc:  # noqa: BLE001 — broadcast is best-effort on connect
        logger.warning("initial state push to %s failed: %s", connection_id, exc)

    logger.info("connected: %s", connection_id)
    return {"statusCode": 200}
