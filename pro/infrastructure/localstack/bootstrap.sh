#!/usr/bin/env bash
# Bootstrap LocalStack with the resources needed to integration-test the
# Lambdas. WebSocket API Gateway is a LocalStack Pro feature — on the
# Community edition the WebSocket pieces will not work, but DynamoDB,
# Lambda, S3, and HTTP API all do.

set -euo pipefail

ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}
REGION=${AWS_DEFAULT_REGION:-us-east-1}
TABLE=${STATE_TABLE:-slides-state}

# LocalStack accepts any non-empty credentials, but the AWS CLI refuses to
# run without them set. Provide dummies so the script works in any env.
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test}
export AWS_DEFAULT_REGION=$REGION

aws() {
  command aws --endpoint-url="$ENDPOINT" --region "$REGION" "$@"
}

echo "→ Waiting for LocalStack at $ENDPOINT ..."
until curl -fsS "$ENDPOINT/_localstack/health" >/dev/null; do
  sleep 1
done
echo "  ready"

echo "→ Creating DynamoDB table '$TABLE' (idempotent)"
if ! aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb update-time-to-live \
    --table-name "$TABLE" \
    --time-to-live-specification "Enabled=true,AttributeName=ttl" >/dev/null
fi

echo "→ Done."
echo
echo "Try:"
echo "  aws --endpoint-url=$ENDPOINT dynamodb scan --table-name $TABLE"
echo
echo "WebSocket API on LocalStack Community is not supported. Use the"
echo "FastAPI local server (scripts/dev.sh) for end-to-end WebSocket"
echo "testing, and LocalStack for verifying the DynamoDB persistence"
echo "and Lambda packaging."
