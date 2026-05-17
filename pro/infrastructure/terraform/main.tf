locals {
  # The set of LocalStack endpoints we override when use_localstack = true.
  # All point at LocalStack's edge port. Services we don't run locally
  # (e.g., CloudFront on Community) gate behind deploy_static = false.
  localstack_endpoints = {
    apigateway     = "http://localhost:4566"
    apigatewayv2   = "http://localhost:4566"
    cloudwatch     = "http://localhost:4566"
    cloudfront     = "http://localhost:4566"
    dynamodb       = "http://localhost:4566"
    iam            = "http://localhost:4566"
    lambda         = "http://localhost:4566"
    logs           = "http://localhost:4566"
    s3             = "http://localhost:4566"
    sts            = "http://localhost:4566"
  }

  resource_prefix = var.project_name
}

provider "aws" {
  region = var.region

  # LocalStack mode: dummy credentials, S3 path-style addressing, no real auth.
  access_key                  = var.use_localstack ? "test" : null
  secret_key                  = var.use_localstack ? "test" : null
  skip_credentials_validation = var.use_localstack
  skip_metadata_api_check     = var.use_localstack
  skip_requesting_account_id  = var.use_localstack
  s3_use_path_style           = var.use_localstack

  dynamic "endpoints" {
    for_each = var.use_localstack ? [1] : []
    content {
      apigateway     = local.localstack_endpoints.apigateway
      apigatewayv2   = local.localstack_endpoints.apigatewayv2
      cloudwatch     = local.localstack_endpoints.cloudwatch
      cloudfront     = local.localstack_endpoints.cloudfront
      dynamodb       = local.localstack_endpoints.dynamodb
      iam            = local.localstack_endpoints.iam
      lambda         = local.localstack_endpoints.lambda
      logs           = local.localstack_endpoints.logs
      s3             = local.localstack_endpoints.s3
      sts            = local.localstack_endpoints.sts
    }
  }
}
