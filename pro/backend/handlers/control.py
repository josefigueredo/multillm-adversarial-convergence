"""HTTP control handler — serves both /control (POST) and /state (GET).

POST /control  → API-key gated; applies a patch, persists state, broadcasts.
GET  /state    → open (read-only debugging endpoint).

API Gateway HTTP API payload format v2 puts the method at
event['requestContext']['http']['method']. REST/v1 puts it at
event['httpMethod']. We support both so the same handler runs on either.

Custom metrics are emitted via CloudWatch Embedded Metric Format (EMF):
we print a JSON line that the CloudWatch Logs agent parses out and
forwards as real metrics — no extra API call, no extra latency.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

from shared import ApiKeyMismatch, apply_patch, require_api_key

from handlers._aws import broadcaster, state_store

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

API_KEY = os.environ.get("SLIDES_API_KEY", "")
METRICS_NAMESPACE = os.environ.get("METRICS_NAMESPACE", "SlidesTemplatePro")


def _response(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _method(event: dict) -> str:
    return (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod", "POST")
    ).upper()


def _emit_broadcast_metric(duration_ms: float, connections: int, stale: int) -> None:
    """Print EMF JSON for CloudWatch to ingest as metrics.

    Spec: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
    """

    emf = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": METRICS_NAMESPACE,
                    "Dimensions": [["Service"]],
                    "Metrics": [
                        {"Name": "BroadcastDurationMs", "Unit": "Milliseconds"},
                        {"Name": "BroadcastConnections", "Unit": "Count"},
                        {"Name": "StaleConnections", "Unit": "Count"},
                    ],
                }
            ],
        },
        "Service": "Broadcast",
        "BroadcastDurationMs": round(duration_ms, 2),
        "BroadcastConnections": connections,
        "StaleConnections": stale,
    }
    # EMF requires the JSON to be on a single log line.
    print(json.dumps(emf))


def handler(event, _context):
    method = _method(event)
    store = state_store()

    if method == "GET":
        # Open read-only state endpoint — useful for debugging and for
        # clients that prefer polling over WebSocket.
        return _response(200, store.load().model_dump())

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    try:
        require_api_key(headers.get("x-api-key"), API_KEY)
    except ApiKeyMismatch as exc:
        return _response(401, {"error": str(exc)})

    try:
        patch = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid JSON body"})
    if not isinstance(patch, dict):
        return _response(400, {"error": "body must be a JSON object"})

    try:
        new_state = apply_patch(store.load(), patch)
    except ValueError as exc:
        return _response(400, {"error": str(exc)})

    store.save(new_state)

    connection_ids = list(store.list_connections())
    started = time.perf_counter()
    stale = asyncio.run(broadcaster().broadcast(new_state, connection_ids))
    duration_ms = (time.perf_counter() - started) * 1000

    for cid in stale:
        store.remove_connection(cid)

    _emit_broadcast_metric(
        duration_ms=duration_ms,
        connections=len(connection_ids),
        stale=len(stale),
    )

    return _response(200, new_state.model_dump())
