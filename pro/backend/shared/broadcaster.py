"""Broadcaster abstraction: fan-out state to every connected viewer.

Local impl talks directly to in-process WebSocket objects. AWS impl posts
to API Gateway Management API which delivers to WebSocket clients held by
API Gateway. Same interface either way.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Iterable, Protocol

from .state import BroadcastState

logger = logging.getLogger(__name__)


class Broadcaster(Protocol):
    async def send_to(self, connection_id: str, state: BroadcastState) -> bool: ...

    async def broadcast(
        self, state: BroadcastState, connection_ids: Iterable[str]
    ) -> list[str]:
        """Send to every id. Return ids of stale connections that failed."""


class InMemoryBroadcaster:
    """For the FastAPI local dev server.

    Holds a registry of WebSocket connections keyed by id. Implements the
    same async ``send_to`` / ``broadcast`` contract the Lambda variant uses,
    so the calling code is identical in both environments.
    """

    def __init__(self) -> None:
        self._sockets: dict[str, Any] = {}

    def register(self, connection_id: str, websocket: Any) -> None:
        self._sockets[connection_id] = websocket

    def unregister(self, connection_id: str) -> None:
        self._sockets.pop(connection_id, None)

    async def send_to(self, connection_id: str, state: BroadcastState) -> bool:
        ws = self._sockets.get(connection_id)
        if ws is None:
            return False
        try:
            await ws.send_text(state.model_dump_json())
            return True
        except Exception as exc:
            logger.warning("send_to(%s) failed: %s", connection_id, exc)
            return False

    async def broadcast(
        self, state: BroadcastState, connection_ids: Iterable[str]
    ) -> list[str]:
        ids = list(connection_ids)
        if not ids:
            return []
        results = await asyncio.gather(
            *(self.send_to(cid, state) for cid in ids), return_exceptions=False
        )
        return [cid for cid, ok in zip(ids, results) if not ok]


class ApiGatewayBroadcaster:
    """Production broadcaster for the WebSocket API Gateway.

    Each ``post_to_connection`` call is an HTTP request to API Gateway. We
    run them in a thread pool because boto3 is sync. A 410 (GoneException)
    means the client disconnected and the connection id is stale.
    """

    def __init__(self, client, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        # ``client`` is ``boto3.client("apigatewaymanagementapi", endpoint_url=...)``
        # injected so tests can substitute a stub.
        self._client = client
        self._sleep = sleep

    async def send_to(self, connection_id: str, state: BroadcastState) -> bool:
        payload = state.model_dump_json().encode("utf-8")
        try:
            await asyncio.to_thread(
                self._client.post_to_connection,
                Data=payload,
                ConnectionId=connection_id,
            )
            return True
        except self._client.exceptions.GoneException:
            return False
        except Exception as exc:
            logger.warning("post_to_connection(%s) failed: %s", connection_id, exc)
            return False

    async def broadcast(
        self, state: BroadcastState, connection_ids: Iterable[str]
    ) -> list[str]:
        ids = list(connection_ids)
        if not ids:
            return []
        results = await asyncio.gather(
            *(self.send_to(cid, state) for cid in ids), return_exceptions=False
        )
        return [cid for cid, ok in zip(ids, results) if not ok]
