"""Guard against silent EMF breakage.

The control handler emits broadcast metrics via a `print()` of EMF JSON
to stdout. CloudWatch Logs parses any log event that's a valid JSON
document with `_aws.CloudWatchMetrics` into real metrics.

If anyone ever refactors `_emit_broadcast_metric` to use `logging.info`,
swap to `sys.stdout = StringIO()` for testing, or rename a field, the
dashboard goes empty *silently* — no error, no warning, just missing
data. This test makes that refactor fail loudly instead.
"""

from __future__ import annotations

import json

from handlers.control import _emit_broadcast_metric


def test_emit_broadcast_metric_writes_single_line_of_valid_emf_json(capsys):
    _emit_broadcast_metric(duration_ms=42.5, connections=3, stale=1)
    captured = capsys.readouterr().out.splitlines()

    # EMF spec: each metric document MUST occupy one log event. If anyone
    # adds a newline or accidentally prints twice, the parser only sees
    # the first chunk and ignores the rest.
    assert len(captured) == 1, f"expected single-line EMF, got: {captured!r}"

    payload = json.loads(captured[0])
    aws = payload["_aws"]
    spec = aws["CloudWatchMetrics"][0]

    assert spec["Namespace"] == "SlidesTemplatePro"
    assert spec["Dimensions"] == [["Service"]]
    assert {m["Name"] for m in spec["Metrics"]} == {
        "BroadcastDurationMs",
        "BroadcastConnections",
        "StaleConnections",
    }
    assert payload["Service"] == "Broadcast"
    assert payload["BroadcastDurationMs"] == 42.5
    assert payload["BroadcastConnections"] == 3
    assert payload["StaleConnections"] == 1
    assert isinstance(aws["Timestamp"], int) and aws["Timestamp"] > 0


def test_emit_broadcast_metric_handles_zero_viewers(capsys):
    """No connected viewers is a legitimate broadcast outcome — must emit valid EMF."""
    _emit_broadcast_metric(duration_ms=0.0, connections=0, stale=0)
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["BroadcastConnections"] == 0
    assert payload["StaleConnections"] == 0
