"""Round-trip test for DynamoDBStateStore using moto's in-memory mock."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from backend.shared import BroadcastState, DynamoDBStateStore


@pytest.fixture
def table():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb.create_table(
            TableName="t",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield ddb.Table("t")


def test_save_and_load_round_trip(table):
    store = DynamoDBStateStore(table)
    state = BroadcastState(slide=7, view="glossary", glossary_term="harness")
    store.save(state)

    loaded = store.load()
    assert loaded.slide == 7
    assert loaded.view == "glossary"
    assert loaded.glossary_term == "harness"


def test_connection_lifecycle(table):
    store = DynamoDBStateStore(table)
    store.add_connection("abc")
    store.add_connection("xyz")
    assert set(store.list_connections()) == {"abc", "xyz"}

    store.remove_connection("abc")
    assert set(store.list_connections()) == {"xyz"}
