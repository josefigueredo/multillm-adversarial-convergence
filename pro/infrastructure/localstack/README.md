# LocalStack integration testing

LocalStack lets you exercise the Terraform pipeline and Lambda code
without an AWS account. The catch: **WebSocket API Gateway, HTTP API
Gateway, and CloudFront are LocalStack Pro features.** On the Community
edition you can still e2e everything that runs INSIDE the Lambdas
(business logic, DynamoDB persistence, IAM), just not the request path
through API Gateway.

## What works on Community

| Service | What you can test |
|---|---|
| DynamoDB | `StateStore` round-trip; TTL on connection items |
| Lambda | Cold start, packaging, dependency resolution, IAM |
| IAM | Role assumption + inline policy enforcement |
| S3 | Static bucket creation (we skip it by default) |
| CloudWatch Logs | Log groups, log retention |

## What does NOT work on Community

| Service | Effect |
|---|---|
| `apigatewayv2` (WebSocket + HTTP API) | The Terraform apply errors out unless `deploy_apigw=false` |
| CloudFront | Same — gated on `deploy_static=false` |
| `apigatewaymanagementapi.post_to_connection` | The broadcast leg is untested; verified by the FastAPI e2e instead |

## Start LocalStack

```bash
make localstack-up
```

That boots the container and creates the DynamoDB table that the
bootstrap script needs.

## Apply the slim Terraform stack

```bash
make tf-localstack-apply
```

This provisions only what Community supports: DynamoDB + 3 Lambdas + IAM
+ CloudWatch log groups. Skips API Gateway and CloudFront automatically.

## Run the e2e test

```bash
make test-e2e
```

`tests/test_e2e_terraform_localstack.py` invokes each Lambda directly
and verifies DynamoDB state mutations. It auto-skips if LocalStack isn't
reachable or if the Terraform stack hasn't been applied.

If you want a single command that brings up LocalStack, applies the
stack, and runs the test:

```bash
make e2e-localstack
```

## Tear down

```bash
make tf-localstack-destroy
make localstack-down
```

`tf-localstack-destroy` removes the AWS resources from LocalStack;
`localstack-down` stops the container and wipes its volume.

## When LocalStack isn't enough

For the WebSocket leg — `$connect` / `$disconnect` / fan-out broadcast
through API Gateway Management API — use one of these instead:

1. **FastAPI e2e** (`tests/test_e2e_local.py`) — same wire protocol,
   pure Python, no Docker. This is the daily-driver test.
2. **Throwaway AWS dev stack** — `make tf-apply` to a personal account
   with a unique `project_name`. Tear down when done.
3. **LocalStack Pro** — adds full `apigatewayv2` support; the same
   tfvars can run unchanged with `deploy_apigw=true`.
