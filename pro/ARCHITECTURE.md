# Architecture

Decisions, tradeoffs, and the seams where you'll extend this thing later.

## The single load-bearing decision

Two abstractions in `backend/shared/`:

```python
class StateStore(Protocol):
    def load(self) -> BroadcastState: ...
    def save(self, state: BroadcastState) -> None: ...
    def add_connection(self, connection_id: str) -> None: ...
    def remove_connection(self, connection_id: str) -> None: ...
    def list_connections(self) -> Iterable[str]: ...

class Broadcaster(Protocol):
    async def send_to(self, connection_id: str, state: BroadcastState) -> bool: ...
    async def broadcast(self, state, connection_ids) -> list[str]: ...
```

Every other module depends on these protocols, not on the implementations.

Local impl uses a Python dict + an asyncio WebSocket set.
Production impl uses DynamoDB + the API Gateway Management API.

This is why the FastAPI server (`backend/local/server.py`) and the
Lambda handlers (`backend/handlers/`) share the actual logic via
`backend/shared/control.py`'s `apply_patch`. Both paths look like:

```python
new_state = apply_patch(store.load(), patch)
store.save(new_state)
stale = await broadcaster.broadcast(new_state, store.list_connections())
for cid in stale:
    store.remove_connection(cid)
```

Swap the impls — the algorithm doesn't change.

## State as protocol

`BroadcastState` is a single Pydantic model with monotonically increasing
`version`. The protocol design choices:

1. **Single object, not a stream of events.** Late joiners get the
   current state on connect, not a replay of every move. Simpler clients,
   no event log to maintain.
2. **Version number, not timestamps.** Clocks are unreliable; counters
   aren't. Clients discard `incoming.version < seen.version`.
3. **Forward-compatible by default.** Adding a field doesn't bump a
   protocol version because clients ignore unknown fields. The frontend
   doesn't need to know about a feature it doesn't use.

The cost: you can't query history. If you need analytics on slide-time
or term-popularity, log control POSTs to CloudWatch or a separate
event sink — don't try to retrofit history onto the state object.

## Why no event bus or message queue

For one presenter and N viewers per session, a queue adds latency and
operational surface for no real benefit:

- API Gateway already buffers per-connection backpressure.
- DynamoDB conditional updates would matter only if we had multiple
  concurrent presenters — and we don't (yet).

If you ever add multiple presenters, the right move is:

1. Add a `presenter_id` column.
2. Use DynamoDB conditional updates keyed on `version` to serialize patches.
3. Reject patches whose `prev_version` doesn't match the server.

That's a known-shape change. Don't add a queue preemptively.

## Why one Pydantic model, not message types

A "command bus" style (different shapes for `NextSlide`, `OpenTerm`,
`SwitchView`) doubles the surface area for no behavioral gain. The
client only cares about the current state; the presenter only knows
how to PATCH the current state. One shape, partial patches, done.

## Why hard navigation between views

Tried: in-page iframe shell with `postMessage`.
Picked: hard navigation (`location.href = ...`).

Tradeoffs:
- Hard nav loses ~200ms to a page load.
- Iframe shell needs a parent↔iframe messaging layer, breaks the
  static-no-build promise, and complicates testing.
- The 200ms is invisible inside a 60-minute presentation.

If you ever need sub-100ms view transitions, build the iframe shell as
a separate `host.html` page that the presenter can opt into. Don't
ship it as the default.

## Backend choice: FastAPI for local, Lambda for prod

| Concern | Local (FastAPI) | Production (Lambda) |
|---|---|---|
| Connection lifetime | held by the server | held by API Gateway |
| Long-running broadcast | trivial | impossible (15-min cap) |
| Connection registry | in-process set | DynamoDB items with TTL |
| Cold start | n/a | ~300ms first viewer-connect |

The interfaces are identical so daily iteration happens locally without
LocalStack overhead. LocalStack is for verifying that the AWS paths
(IAM, DynamoDB serialization) actually work — it's not the dev loop.

## Auth: API key is enough for now

Single shared key, validated with `hmac.compare_digest`. Trade-offs:

- **Pros**: zero infrastructure, presenter just types or stores it.
- **Cons**: key rotation = redeploy + reconfigure every presenter device.
- **When to upgrade**: if you ever expose `/control` to people outside
  the presenting team, replace with a JWT authorizer (HTTP API supports
  this natively) or Cognito.

Viewers are NOT authenticated. The WebSocket is open by design — you
WANT random audience members to connect. If you ever need private
viewing, add a JWT to the WS URL and a Lambda authorizer to `$connect`.

## Extension points

| You want to… | Touch this |
|---|---|
| Add a new view (e.g., live cursor) | `BroadcastState.view` literal + `VIEW_URLS` maps in `docs/showcase/sync/` |
| Add a presenter control (e.g., highlight region) | New optional field on `BroadcastState`, add to `ALLOWED_FIELDS` |
| Send per-viewer state (e.g., personal nudge) | Add a `recipient: Optional[str]` field; broadcaster filters by id |
| Track usage analytics | Log `control` POSTs in the Lambda handler to CloudWatch + a fanout to Kinesis |
| Multi-presenter | `presenter_id` field on `BroadcastState` + DDB conditional updates |
| Private viewing | JWT in WS URL + Lambda authorizer on `$connect` |
| Sub-100ms view changes | Build an iframe-shell `host.html` page (not the default) |

## Anti-extension points

| You want to… | Don't |
|---|---|
| "Event source" history | Use a separate event log table, don't pile it onto state |
| Roll your own reconnection logic | The browser `EventSource`-style backoff in sync.js is enough |
| Server-driven layout (push HTML) | Keep HTML static; broadcast IDs and indices, not markup |
| Authenticate viewers as presenters | Different auth surface, different threat model — keep them separate |

## Migration tells

The architecture starts to creak when:

- **You add a third backend (mobile? embedded? extension?).** That's
  when you create a `slides-protocol` package with the state model and
  ship it as an SDK.
- **Connection count exceeds ~1k per Lambda invocation.** Switch from
  scan-and-broadcast to SNS fan-out or Momento Topics.
- **Multi-region audience with shared state.** DynamoDB Global Tables
  is the path of least surprise.

Until then, this is the right shape.
