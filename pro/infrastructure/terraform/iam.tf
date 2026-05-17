# ── Lambda execution role ────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.resource_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_inline" {
  # CloudWatch logs
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }

  # DynamoDB CRUD on the state table only
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:Scan",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.state.arn]
  }

  # API Gateway WebSocket management (post_to_connection / delete_connection)
  # Scoped to the websocket api only. Skipped when apigw isn't deployed.
  dynamic "statement" {
    for_each = var.deploy_apigw ? [1] : []
    content {
      actions   = ["execute-api:ManageConnections"]
      resources = ["arn:aws:execute-api:${var.region}:*:${aws_apigatewayv2_api.ws[0].id}/*"]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.resource_prefix}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_inline.json
}
