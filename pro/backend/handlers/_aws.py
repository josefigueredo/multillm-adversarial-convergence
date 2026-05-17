"""AWS resource wiring shared by every Lambda handler.

Keeps the boto3 clients lazy so cold-start cost is paid once per
container, then reused for every warm invocation.

The apigatewaymanagementapi client overrides botocore's default
``max_pool_connections = 10`` because the broadcast loop fires every
post_to_connection concurrently — with the default we'd serialize 7,000
viewers through a 10-slot pool and time out on Lambda's 15s limit.
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3
from botocore.config import Config

from shared import (
    ApiGatewayBroadcaster,
    DynamoDBStateStore,
)

# Tunable: how many parallel HTTP connections the broadcaster can hold
# open to API Gateway Management API. 100 keeps the fan-out wall-time
# at ~2s for 7,000 viewers (each post ≈ 20ms). Raise if you grow.
WS_POOL_SIZE = int(os.environ.get("WS_POOL_SIZE", "100"))

TABLE_NAME = os.environ.get("STATE_TABLE", "slides-state")


@lru_cache(maxsize=1)
def state_store() -> DynamoDBStateStore:
    table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return DynamoDBStateStore(table)


@lru_cache(maxsize=1)
def _management_endpoint() -> str:
    endpoint = os.environ.get("WS_MANAGEMENT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("WS_MANAGEMENT_ENDPOINT env var is required")
    return endpoint


@lru_cache(maxsize=1)
def broadcaster() -> ApiGatewayBroadcaster:
    client = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=_management_endpoint(),
        config=Config(
            max_pool_connections=WS_POOL_SIZE,
            retries={"max_attempts": 2, "mode": "adaptive"},
        ),
    )
    return ApiGatewayBroadcaster(client)
