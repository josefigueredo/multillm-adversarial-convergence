"""WebSocket $disconnect handler.

Best-effort cleanup. API Gateway may also drop the connection silently
without firing $disconnect — the TTL on the connection item handles that
case so the table doesn't accumulate stale entries.
"""

from __future__ import annotations

import logging

from handlers._aws import state_store

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, _context):
    connection_id = event["requestContext"]["connectionId"]
    state_store().remove_connection(connection_id)
    logger.info("disconnected: %s", connection_id)
    return {"statusCode": 200}
