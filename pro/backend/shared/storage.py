"""Storage abstraction: same business logic, swappable backends.

`StateStore` holds the broadcast state. Local dev uses ``InMemoryStateStore``
(a single object in memory). AWS uses ``DynamoDBStateStore`` (a single item
in a DynamoDB table). Both implement the same three methods.
"""

from __future__ import annotations

import time
from typing import Iterable, Protocol

from .state import BroadcastState

STATE_KEY = "state"


class StateStore(Protocol):
    """Stores the current broadcast state."""

    def load(self) -> BroadcastState: ...
    def save(self, state: BroadcastState) -> None: ...

    def add_connection(self, connection_id: str) -> None: ...
    def remove_connection(self, connection_id: str) -> None: ...
    def list_connections(self) -> Iterable[str]: ...


class InMemoryStateStore:
    """Used by the FastAPI local dev server and unit tests."""

    def __init__(self) -> None:
        self._state = BroadcastState()
        self._connections: set[str] = set()

    def load(self) -> BroadcastState:
        return self._state

    def save(self, state: BroadcastState) -> None:
        self._state = state

    def add_connection(self, connection_id: str) -> None:
        self._connections.add(connection_id)

    def remove_connection(self, connection_id: str) -> None:
        self._connections.discard(connection_id)

    def list_connections(self) -> Iterable[str]:
        return list(self._connections)


class DynamoDBStateStore:
    """Used by the production Lambda handlers.

    One table holds two kinds of items:
      - ``pk = "state"``                — the BroadcastState JSON blob
      - ``pk = "conn#<connectionId>"``  — one item per WebSocket connection,
                                          with a TTL to garbage-collect leaks
    """

    CONN_PREFIX = "conn#"
    CONN_TTL_HOURS = 12

    def __init__(self, table) -> None:
        # ``table`` is a ``boto3.resource("dynamodb").Table(name)`` handle.
        # Passing it in (rather than constructing inside) lets tests inject
        # a moto-backed table without monkey-patching boto3.
        self._table = table

    def load(self) -> BroadcastState:
        item = self._table.get_item(Key={"pk": STATE_KEY}).get("Item")
        if not item:
            return BroadcastState()
        item.pop("pk", None)
        return BroadcastState.model_validate(item)

    def save(self, state: BroadcastState) -> None:
        item = state.model_dump()
        item["pk"] = STATE_KEY
        self._table.put_item(Item=item)

    def add_connection(self, connection_id: str) -> None:
        self._table.put_item(
            Item={
                "pk": f"{self.CONN_PREFIX}{connection_id}",
                "ttl": int(time.time()) + self.CONN_TTL_HOURS * 3600,
            }
        )

    def remove_connection(self, connection_id: str) -> None:
        self._table.delete_item(Key={"pk": f"{self.CONN_PREFIX}{connection_id}"})

    def list_connections(self) -> Iterable[str]:
        # Scan is fine here: connection-count is bounded by concurrent
        # viewers, not by history. For thousands of viewers, swap to a GSI.
        items = self._table.scan(
            FilterExpression="begins_with(pk, :p)",
            ExpressionAttributeValues={":p": self.CONN_PREFIX},
            ProjectionExpression="pk",
        ).get("Items", [])
        return [item["pk"][len(self.CONN_PREFIX):] for item in items]
