variable "project_name" {
  description = "Resource name prefix"
  type        = string
  default     = "slides-template-pro"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "api_key" {
  description = "Shared X-API-Key presented by the presenter for /control"
  type        = string
  sensitive   = true
}

variable "use_localstack" {
  description = "Point providers at LocalStack (http://localhost:4566) for local integration testing"
  type        = bool
  default     = false
}

variable "deploy_static" {
  description = "Provision S3 + CloudFront for the showcase. Set false on LocalStack (CloudFront isn't supported)."
  type        = bool
  default     = true
}

variable "deploy_apigw" {
  description = "Provision the WebSocket + HTTP API Gateway v2 resources. Set false on LocalStack Community (apigatewayv2 is Pro)."
  type        = bool
  default     = true
}

variable "deploy_observability" {
  description = "Provision the CloudWatch dashboard + alarms. Set false on LocalStack (dashboards aren't well supported)."
  type        = bool
  default     = true
}

variable "alarm_sns_topic_arn" {
  description = "Optional SNS topic ARN to receive alarm notifications. Empty = no notifications."
  type        = string
  default     = ""
}

variable "lambda_log_retention_days" {
  description = "CloudWatch log retention for Lambda logs"
  type        = number
  default     = 14
}

variable "lambda_architecture" {
  description = "arm64 is cheaper and faster on Graviton2; switch to x86_64 if you need a layer that only ships on x86"
  type        = string
  default     = "arm64"
  validation {
    condition     = contains(["arm64", "x86_64"], var.lambda_architecture)
    error_message = "lambda_architecture must be arm64 or x86_64"
  }
}
