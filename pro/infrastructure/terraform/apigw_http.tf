# ── HTTP API: presenter POSTs control + viewers GET state ───────────
resource "aws_apigatewayv2_api" "http" {
  count         = var.deploy_apigw ? 1 : 0
  name          = "${local.resource_prefix}-http"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_headers = ["content-type", "x-api-key"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_integration" "control" {
  count                  = var.deploy_apigw ? 1 : 0
  api_id                 = aws_apigatewayv2_api.http[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.control.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "control_post" {
  count     = var.deploy_apigw ? 1 : 0
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "POST /control"
  target    = "integrations/${aws_apigatewayv2_integration.control[0].id}"
}

resource "aws_apigatewayv2_route" "control_get_state" {
  count     = var.deploy_apigw ? 1 : 0
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "GET /state"
  target    = "integrations/${aws_apigatewayv2_integration.control[0].id}"
}

resource "aws_lambda_permission" "control_invoke" {
  count         = var.deploy_apigw ? 1 : 0
  statement_id  = "AllowHttpAPIControl"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.control.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}

resource "aws_apigatewayv2_stage" "http" {
  count       = var.deploy_apigw ? 1 : 0
  api_id      = aws_apigatewayv2_api.http[0].id
  name        = "$default"
  auto_deploy = true
}
