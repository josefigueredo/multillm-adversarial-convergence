output "websocket_url" {
  description = "WebSocket endpoint viewers connect to"
  value = var.deploy_apigw ? (
    "wss://${aws_apigatewayv2_api.ws[0].id}.execute-api.${var.region}.amazonaws.com/${aws_apigatewayv2_stage.ws[0].name}"
  ) : null
}

output "control_url" {
  description = "HTTP endpoint the presenter POSTs to"
  value       = var.deploy_apigw ? "${aws_apigatewayv2_api.http[0].api_endpoint}/control" : null
}

output "state_url" {
  description = "HTTP endpoint exposing the current state (read-only)"
  value       = var.deploy_apigw ? "${aws_apigatewayv2_api.http[0].api_endpoint}/state" : null
}

output "control_lambda_name" {
  description = "Name of the control Lambda — useful for direct invocation in tests"
  value       = aws_lambda_function.control.function_name
}

output "state_table_name" {
  description = "DynamoDB table holding state + connection registry"
  value       = aws_dynamodb_table.state.name
}

output "static_bucket" {
  description = "S3 bucket holding the showcase assets (null if deploy_static=false)"
  value       = var.deploy_static ? aws_s3_bucket.static[0].bucket : null
}

output "static_url" {
  description = "CloudFront URL for the showcase (null if deploy_static=false)"
  value       = var.deploy_static ? "https://${aws_cloudfront_distribution.static[0].domain_name}" : null
}

output "dashboard_url" {
  description = "AWS console URL for the CloudWatch dashboard (null if deploy_observability=false)"
  value = var.deploy_observability ? (
    "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${aws_cloudwatch_dashboard.main[0].dashboard_name}"
  ) : null
}
