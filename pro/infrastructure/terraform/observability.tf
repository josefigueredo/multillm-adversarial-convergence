# ── Observability ────────────────────────────────────────────────────
# Gated on var.deploy_observability so the LocalStack profile can skip
# dashboards (LocalStack Community has limited CloudWatch dashboard
# support). The Lambdas still emit EMF metrics regardless — they just
# land in CloudWatch only when the agent is forwarding them, which
# requires a real AWS account.

locals {
  emf_namespace = "SlidesTemplatePro"

  # Aggregate metric definitions so dashboard + alarms share one source of truth.
  broadcast_metrics = {
    duration_p50 = ["${local.emf_namespace}", "BroadcastDurationMs", "Service", "Broadcast", { stat = "p50" }]
    duration_p99 = ["${local.emf_namespace}", "BroadcastDurationMs", "Service", "Broadcast", { stat = "p99" }]
    duration_max = ["${local.emf_namespace}", "BroadcastDurationMs", "Service", "Broadcast", { stat = "Maximum" }]
    connections  = ["${local.emf_namespace}", "BroadcastConnections", "Service", "Broadcast", { stat = "Maximum" }]
    stale        = ["${local.emf_namespace}", "StaleConnections", "Service", "Broadcast", { stat = "Sum" }]
  }
}

# ── Dashboard ────────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  count          = var.deploy_observability ? 1 : 0
  dashboard_name = local.resource_prefix

  dashboard_body = jsonencode({
    widgets = [
      # Row 1: broadcast story
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Broadcast wall-time (ms) — keep p99 under 5,000ms"
          region = var.region
          view   = "timeSeries"
          stacked = false
          period = 60
          metrics = [
            [local.emf_namespace, "BroadcastDurationMs", "Service", "Broadcast", { stat = "p50", label = "p50" }],
            ["...", { stat = "p90", label = "p90" }],
            ["...", { stat = "p99", label = "p99" }],
            ["...", { stat = "Maximum", label = "max" }],
          ]
          yAxis = { left = { min = 0, label = "ms" } }
          annotations = {
            horizontal = [
              { value = 5000, label = "Tier 2 budget", color = "#d62728" },
              { value = 2000, label = "comfortable", color = "#2ca02c" },
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Connected viewers (per broadcast)"
          region = var.region
          view   = "timeSeries"
          period = 60
          metrics = [
            [local.emf_namespace, "BroadcastConnections", "Service", "Broadcast", { stat = "Maximum", label = "max viewers" }],
            ["...", { stat = "Average", label = "avg viewers" }],
            [local.emf_namespace, "StaleConnections", "Service", "Broadcast", { stat = "Sum", label = "stale pruned" }],
          ]
          yAxis = { left = { min = 0, label = "count" } }
        }
      },

      # Row 2: Lambda health
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Lambda invocations"
          region = var.region
          view   = "timeSeries"
          stacked = true
          period = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.control.function_name],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.connect.function_name],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.disconnect.function_name],
          ]
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Lambda errors"
          region = var.region
          view   = "timeSeries"
          stacked = false
          period = 60
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.control.function_name, { color = "#d62728" }],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.connect.function_name, { color = "#ff7f0e" }],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.disconnect.function_name, { color = "#9467bd" }],
          ]
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Lambda duration p99 (ms)"
          region = var.region
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.control.function_name, { stat = "p99" }],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.connect.function_name, { stat = "p99" }],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.disconnect.function_name, { stat = "p99" }],
          ]
        }
      },

      # Row 3: DynamoDB capacity
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB consumed capacity"
          region = var.region
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.state.name],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.state.name],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB throttled requests (should be zero)"
          region = var.region
          view   = "timeSeries"
          period = 60
          metrics = [
            ["AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.state.name],
            ["AWS/DynamoDB", "UserErrors", "TableName", aws_dynamodb_table.state.name],
          ]
        }
      },
    ]
  })
}

# ── Alarms ───────────────────────────────────────────────────────────
#
# Three alarms protect the operational invariants we actually care about:
#   1. Broadcast latency budget — if p99 ever exceeds 5s, fan-out is
#      approaching the Lambda timeout and we need to scale.
#   2. Control Lambda errors — any error in 5min means a real failure.
#   3. Lambda throttling — concurrency cap hit; account quota too tight.

resource "aws_cloudwatch_metric_alarm" "broadcast_duration" {
  count = var.deploy_observability ? 1 : 0

  alarm_name          = "${local.resource_prefix}-broadcast-duration-p99"
  alarm_description   = "Broadcast fan-out latency p99 exceeds 5s — investigate viewer count, pool size, or split fan-out across Lambdas."
  namespace           = local.emf_namespace
  metric_name         = "BroadcastDurationMs"
  extended_statistic  = "p99"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 5000
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  dimensions = { Service = "Broadcast" }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
}

resource "aws_cloudwatch_metric_alarm" "control_errors" {
  count = var.deploy_observability ? 1 : 0

  alarm_name          = "${local.resource_prefix}-control-errors"
  alarm_description   = "Control Lambda returned an error — presenter actions failing."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 60
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  dimensions = { FunctionName = aws_lambda_function.control.function_name }

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count = var.deploy_observability ? 1 : 0

  alarm_name          = "${local.resource_prefix}-lambda-throttles"
  alarm_description   = "A Lambda hit the concurrency cap — bump account quota or add reserved concurrency."
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 60
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  # No dimensions — catches throttles on any function in the account.
  # Tighten later if you have other Lambdas in the same region.

  alarm_actions = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
  ok_actions    = var.alarm_sns_topic_arn != "" ? [var.alarm_sns_topic_arn] : []
}
