"""Broadcaster reports stale connections and skips dead sockets."""

import pytest

from backend.shared import BroadcastState, InMemoryBroadcaster


class FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    async def send_text(self, payload: str) -> None:
        if self.fail:
            raise RuntimeError("socket closed")
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_broadcast_to_healthy_connections():
    b = InMemoryBroadcaster()
    a, c = FakeWebSocket(), FakeWebSocket()
    b.register("a", a)
    b.register("c", c)
    stale = await b.broadcast(BroadcastState(slide=2), ["a", "c"])
    assert stale == []
    assert len(a.sent) == 1 and len(c.sent) == 1


@pytest.mark.asyncio
async def test_broadcast_reports_failed_connections_as_stale():
    b = InMemoryBroadcaster()
    a = FakeWebSocket()
    dead = FakeWebSocket(fail=True)
    b.register("a", a)
    b.register("dead", dead)
    stale = await b.broadcast(BroadcastState(slide=2), ["a", "dead"])
    assert stale == ["dead"]
