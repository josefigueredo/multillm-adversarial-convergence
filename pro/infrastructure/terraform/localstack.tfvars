# Apply with: terraform apply -var-file=localstack.tfvars
#
# LocalStack Community supports DynamoDB + Lambda + S3 + IAM, but NOT:
#   - apigatewayv2 (WebSocket / HTTP API)        → deploy_apigw  = false
#   - CloudFront                                 → deploy_static = false
#
# What this slim stack lets you e2e:
#   - Terraform plan + apply pipeline is valid
#   - Lambda packaging + dependency layer works
#   - IAM permissions are correct
#   - Direct Lambda invoke writes state to DynamoDB
#
# The WebSocket broadcast leg is tested via the FastAPI e2e in tests/test_e2e_local.py.

use_localstack       = true
deploy_static        = false
deploy_apigw         = false
deploy_observability = false
api_key              = "local-e2e-key"
project_name         = "slides-pro-e2e"
