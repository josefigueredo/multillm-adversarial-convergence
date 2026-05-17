# Terraform deployment

Two profiles share one configuration:

| Profile | Command | What gets deployed |
|---|---|---|
| Real AWS | `make tf-apply` | DynamoDB, 3 Lambdas, WebSocket API, HTTP API, S3, CloudFront |
| LocalStack Community | `make tf-localstack-apply` | DynamoDB, 3 Lambdas (no API Gateway, no CloudFront) |

The LocalStack profile sets `deploy_apigw=false` and `deploy_static=false`
because both are LocalStack Pro features. It's still enough to e2e the
business logic — see `tests/test_e2e_terraform_localstack.py`.

## Files

| File | Role |
|---|---|
| `versions.tf` | Terraform + provider version constraints |
| `main.tf` | AWS provider, LocalStack endpoint overlay |
| `variables.tf` | `api_key`, `use_localstack`, `deploy_apigw`, `deploy_static`, etc. |
| `dynamodb.tf` | State table with TTL on the connection items |
| `lambda_build.tf` | pip install + zip pipeline (uses `null_resource`) |
| `iam.tf` | Lambda execution role + least-privilege inline policy |
| `lambda.tf` | The three function resources + CloudWatch log groups |
| `apigw_ws.tf` | WebSocket API + `$connect` / `$disconnect` routes |
| `apigw_http.tf` | HTTP API + `POST /control` + `GET /state` |
| `static.tf` | S3 + CloudFront for the showcase folder |
| `outputs.tf` | WebSocket URL, control URL, bucket names, etc. |
| `localstack.tfvars` | Variable values for the LocalStack profile |

## Deploy to AWS

```bash
export SLIDES_API_KEY=$(openssl rand -hex 24)
make tf-init
make tf-plan      # review what's about to change
make tf-apply
make deploy-static   # rsync docs/ to the S3 bucket
```

Outputs include the WebSocket URL the viewer pages connect to and the
HTTP API URL the presenter POSTs to. Plug them into a runtime config
script tag in your presenter HTML.

## Deploy to LocalStack

```bash
make localstack-up
make tf-localstack-apply
make test-e2e        # runs the LocalStack + FastAPI e2e suites
```

Or in one shot:

```bash
make e2e-localstack
```

## Why no Lambda Layer

We bundle pydantic directly into each function's zip instead of using a
Lambda Layer. Reasons:

1. **LocalStack Community has quirks with layered imports.** The Lambda
   image loads layers from `/opt`, but some paths fail to resolve in
   Community edition. Bundling in `/var/task` works identically locally
   and on AWS.
2. **pydantic compressed is ~2.5MB.** Multiplied across 3 functions
   that's 7.5MB extra in the artifact — invisible against the Lambda
   size limit (250MB unzipped) and well worth the simpler config.
3. **Layer ARNs are versioned forever.** Bumping a layer creates a new
   version that the function must explicitly point at; with bundled
   deps you only have one resource graph to reason about.

If function size ever becomes a problem (say you grow to 20+ Lambdas
that share deps), revisit. Until then, bundle.

## Build pipeline

`null_resource.build_code` runs on every change to `backend/handlers/`,
`backend/shared/`, or `backend/requirements.txt`:

```bash
rm -rf build/code
mkdir build/code
cp -R backend/handlers build/code/handlers
cp -R backend/shared   build/code/shared
pip install --target build/code \
            --platform manylinux2014_aarch64 \
            --python-version 3.12 \
            --only-binary=:all: \
            -r backend/requirements.txt
```

`archive_file.code` zips the staged directory. The Lambdas reference
that zip via `source_code_hash` so Terraform detects changes and
redeploys without manual intervention.

## Tear down

```bash
make tf-destroy           # AWS
make tf-localstack-destroy && make localstack-down   # local
```
