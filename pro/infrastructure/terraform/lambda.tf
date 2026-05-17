locals {
  # When the WS API isn't deployed (LocalStack Community) we still need a
  # value for the env var — the broadcaster only dials this if there are
  # connected clients, so a placeholder is harmless for direct-invoke tests.
  ws_management_endpoint = var.deploy_apigw ? (
    "https://${aws_apigatewayv2_api.ws[0].id}.execute-api.${var.region}.amazonaws.com/${aws_apigatewayv2_stage.ws[0].name}"
  ) : "https://placeholder.invalid/prod"

  common_lambda_env = {
    STATE_TABLE            = aws_dynamodb_table.state.name
    WS_MANAGEMENT_ENDPOINT = local.ws_management_endpoint
  }
}

# ── $connect handler ─────────────────────────────────────────────────
resource "aws_lambda_function" "connect" {
  function_name = "${local.resource_prefix}-connect"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "handlers.connect.handler"
  architectures = [var.lambda_architecture]
  # 15s gives boto3 room to resolve a placeholder endpoint (LocalStack
  # Community) before we abandon the initial-state push. The connection
  # is registered before the push, so a timeout there is recoverable.
  timeout     = 15
  memory_size = 256

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  environment {
    variables = local.common_lambda_env
  }
}

resource "aws_cloudwatch_log_group" "connect" {
  name              = "/aws/lambda/${aws_lambda_function.connect.function_name}"
  retention_in_days = var.lambda_log_retention_days
}

# ── $disconnect handler ──────────────────────────────────────────────
resource "aws_lambda_function" "disconnect" {
  function_name = "${local.resource_prefix}-disconnect"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "handlers.disconnect.handler"
  architectures = [var.lambda_architecture]
  timeout       = 10
  memory_size   = 256

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  environment {
    variables = local.common_lambda_env
  }
}

resource "aws_cloudwatch_log_group" "disconnect" {
  name              = "/aws/lambda/${aws_lambda_function.disconnect.function_name}"
  retention_in_days = var.lambda_log_retention_days
}

# ── POST /control handler ────────────────────────────────────────────
# Sized for fan-out to ~7,000 concurrent viewers per broadcast:
#   - 1769MB ≈ one full vCPU (boost asyncio executor throughput)
#   - 30s timeout to give the boto3 pool headroom under unexpected
#     network latency to the API Gateway Management API
resource "aws_lambda_function" "control" {
  function_name = "${local.resource_prefix}-control"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "handlers.control.handler"
  architectures = [var.lambda_architecture]
  timeout       = 30
  memory_size   = 1769

  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  environment {
    variables = merge(local.common_lambda_env, {
      SLIDES_API_KEY = var.api_key
    })
  }
}

resource "aws_cloudwatch_log_group" "control" {
  name              = "/aws/lambda/${aws_lambda_function.control.function_name}"
  retention_in_days = var.lambda_log_retention_days
}
