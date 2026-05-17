"""End-to-end test: provision the slim Terraform stack to LocalStack,
invoke each Lambda directly, verify DynamoDB persistence.

This proves the whole pipeline:
  - Terraform configuration is valid and applies cleanly
  - Lambda packaging (source + pip deps) imports without errors
  - IAM is correct (Lambda → DynamoDB read/write works)
  - Business logic runs end-to-end through the real handler entry points

The WebSocket broadcast leg is NOT exercised here (apigatewayv2 is a
LocalStack Pro feature). That leg is covered by tests/test_e2e_local.py
which runs against the FastAPI server.

Prerequisites:
  - LocalStack running on :4566 (docker compose up in infrastructure/localstack)
  - terraform on PATH
  - python3.12 on PATH (for the build pipeline)
  - `terraform apply -var-file=localstack.tfvars` already run, OR
    set ENV E2E_TF_AUTO_APPLY=1 to let the test apply itself

If any prereq is missing, the test SKIPS rather than failing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request

import pytest

LOCALSTACK_URL = "http://localhost:4566"
TF_DIR = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "terraform")
API_KEY = "local-e2e-key"
PROJECT = "slides-pro-e2e"


def _localstack_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{LOCALSTACK_URL}/_localstack/health", timeout=1) as r:
            data = json.load(r)
        # LocalStack reports "available" for cold services, "running" for warm.
        # Either is fine — we just need the service to be reachable.
        return data.get("services", {}).get("dynamodb") in {"available", "running"}
    except Exception:
        return False


def _terraform_outputs() -> dict | None:
    if not shutil.which("terraform"):
        return None
    try:
        out = subprocess.check_output(
            ["terraform", "-chdir=" + TF_DIR, "output", "-json"],
            stderr=subprocess.DEVNULL,
        )
        return json.loads(out)
    except subprocess.CalledProcessError:
        return None


def _maybe_apply():
    if os.environ.get("E2E_TF_AUTO_APPLY") != "1":
        return
    subprocess.check_call(
        ["terraform", "-chdir=" + TF_DIR, "init", "-input=false", "-upgrade=false"]
    )
    subprocess.check_call(
        [
            "terraform",
            "-chdir=" + TF_DIR,
            "apply",
            "-var-file=localstack.tfvars",
            "-auto-approve",
            "-input=false",
        ]
    )


@pytest.fixture(scope="module")
def deployed():
    if not _localstack_reachable():
        pytest.skip("LocalStack not reachable on :4566")
    if not shutil.which("terraform"):
        pytest.skip("terraform not on PATH")

    _maybe_apply()

    outputs = _terraform_outputs()
    if not outputs or "control_lambda_name" not in outputs:
        pytest.skip(
            "Terraform stack not applied. Run `make tf-localstack-apply` first or set E2E_TF_AUTO_APPLY=1."
        )

    boto3 = pytest.importorskip("boto3")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

    return {
        "lambda": boto3.client("lambda", endpoint_url=LOCALSTACK_URL),
        "ddb": boto3.resource("dynamodb", endpoint_url=LOCALSTACK_URL).Table(
            outputs["state_table_name"]["value"]
        ),
        "control_name": outputs["control_lambda_name"]["value"],
        "connect_name": f"{PROJECT}-connect",
        "disconnect_name": f"{PROJECT}-disconnect",
    }


def _invoke(lam, name: str, event: dict) -> dict:
    resp = lam.invoke(FunctionName=name, Payload=json.dumps(event).encode())
    return json.loads(resp["Payload"].read().decode())


def _post(headers: dict, body: dict) -> dict:
    return {
        "requestContext": {"http": {"method": "POST"}},
        "headers": headers,
        "body": json.dumps(body),
    }


def test_control_post_persists_state(deployed):
    """A valid POST writes the patched state to DynamoDB with version 1."""
    payload = _invoke(
        deployed["lambda"],
        deployed["control_name"],
        _post({"x-api-key": API_KEY}, {"slide": 7, "view": "glossary", "glossary_term": "harness"}),
    )
    assert payload["statusCode"] == 200, payload
    body = json.loads(payload["body"])
    assert body["slide"] == 7
    assert body["view"] == "glossary"
    assert body["glossary_term"] == "harness"
    assert body["version"] >= 1

    item = deployed["ddb"].get_item(Key={"pk": "state"}).get("Item", {})
    assert int(item["slide"]) == 7
    assert item["view"] == "glossary"
    assert int(item["version"]) == body["version"]


def test_control_post_bumps_version(deployed):
    """Successive patches monotonically bump the version counter."""
    first = json.loads(
        _invoke(deployed["lambda"], deployed["control_name"], _post({"x-api-key": API_KEY}, {"slide": 1}))["body"]
    )
    second = json.loads(
        _invoke(deployed["lambda"], deployed["control_name"], _post({"x-api-key": API_KEY}, {"slide": 2}))["body"]
    )
    assert second["version"] == first["version"] + 1


def test_control_post_rejects_wrong_key(deployed):
    payload = _invoke(
        deployed["lambda"],
        deployed["control_name"],
        _post({"x-api-key": "nope"}, {"slide": 9}),
    )
    assert payload["statusCode"] == 401


def test_control_post_rejects_unknown_field(deployed):
    payload = _invoke(
        deployed["lambda"],
        deployed["control_name"],
        _post({"x-api-key": API_KEY}, {"nope": 1}),
    )
    assert payload["statusCode"] == 400
    assert "nope" in payload["body"]


def test_control_get_state_is_open(deployed):
    """GET /state requires no auth — useful for debugging and polling clients."""
    payload = _invoke(
        deployed["lambda"],
        deployed["control_name"],
        {"requestContext": {"http": {"method": "GET"}}, "headers": {}},
    )
    assert payload["statusCode"] == 200
    body = json.loads(payload["body"])
    assert "view" in body and "slide" in body and "version" in body


def test_connect_registers_connection(deployed):
    cid = "test-conn-abc"
    payload = _invoke(
        deployed["lambda"],
        deployed["connect_name"],
        {"requestContext": {"connectionId": cid}},
    )
    # The connect handler attempts to push current state to the new viewer.
    # When the WS management endpoint is a placeholder (LocalStack Community
    # without apigatewayv2), that call fails — broadcaster.send_to catches
    # the exception and returns False, so the Lambda still returns success.
    # If the Lambda timed out or crashed, surface the full payload so a
    # debugger doesn't have to guess.
    assert payload.get("statusCode") == 200, f"connect lambda failed: {payload}"

    items = (
        deployed["ddb"]
        .scan(
            FilterExpression="begins_with(pk, :p)",
            ExpressionAttributeValues={":p": "conn#"},
            ProjectionExpression="pk",
        )
        .get("Items", [])
    )
    assert any(item["pk"] == f"conn#{cid}" for item in items)


def test_disconnect_removes_connection(deployed):
    cid = "test-conn-zzz"
    deployed["ddb"].put_item(Item={"pk": f"conn#{cid}"})

    payload = _invoke(
        deployed["lambda"],
        deployed["disconnect_name"],
        {"requestContext": {"connectionId": cid}},
    )
    assert payload["statusCode"] == 200

    items = (
        deployed["ddb"]
        .scan(
            FilterExpression="begins_with(pk, :p)",
            ExpressionAttributeValues={":p": "conn#"},
            ProjectionExpression="pk",
        )
        .get("Items", [])
    )
    assert not any(item["pk"] == f"conn#{cid}" for item in items)
