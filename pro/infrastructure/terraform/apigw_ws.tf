# ── WebSocket API: viewers connect here ───────────────────────────────
# Gated on var.deploy_apigw because apigatewayv2 is a LocalStack Pro feature.
# The Lambdas themselves still deploy, so direct-invoke e2e tests work.

resource "aws_apigatewayv2_api" "ws" {
  count                      = var.deploy_apigw ? 1 : 0
  name                       = "${local.resource_prefix}-ws"
  protocol_type              = "WEBSOCKET"
  route_selection_expression = "$request.body.action"
}

# ── $connect ─────────────────────────────────────────────────────────
resource "aws_apigatewayv2_integration" "connect" {
  count                     = var.deploy_apigw ? 1 : 0
  api_id                    = aws_apigatewayv2_api.ws[0].id
  integration_type          = "AWS_PROXY"
  integration_uri           = aws_lambda_function.connect.invoke_arn
  content_handling_strategy = "CONVERT_TO_TEXT"
  passthrough_behavior      = "WHEN_NO_MATCH"
}

resource "aws_apigatewayv2_route" "connect" {
  count     = var.deploy_apigw ? 1 : 0
  api_id    = aws_apigatewayv2_api.ws[0].id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.connect[0].id}"
}

resource "aws_lambda_permission" "connect_invoke" {
  count         = var.deploy_apigw ? 1 : 0
  statement_id  = "AllowAPIGWConnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.connect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws[0].execution_arn}/*"
}

# ── $disconnect ──────────────────────────────────────────────────────
resource "aws_apigatewayv2_integration" "disconnect" {
  count                     = var.deploy_apigw ? 1 : 0
  api_id                    = aws_apigatewayv2_api.ws[0].id
  integration_type          = "AWS_PROXY"
  integration_uri           = aws_lambda_function.disconnect.invoke_arn
  content_handling_strategy = "CONVERT_TO_TEXT"
  passthrough_behavior      = "WHEN_NO_MATCH"
}

resource "aws_apigatewayv2_route" "disconnect" {
  count     = var.deploy_apigw ? 1 : 0
  api_id    = aws_apigatewayv2_api.ws[0].id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.disconnect[0].id}"
}

resource "aws_lambda_permission" "disconnect_invoke" {
  count         = var.deploy_apigw ? 1 : 0
  statement_id  = "AllowAPIGWDisconnect"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.disconnect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ws[0].execution_arn}/*"
}

# ── Stage (auto-deploys) ─────────────────────────────────────────────
resource "aws_apigatewayv2_stage" "ws" {
  count       = var.deploy_apigw ? 1 : 0
  api_id      = aws_apigatewayv2_api.ws[0].id
  name        = "prod"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }
}
