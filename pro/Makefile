.PHONY: install dev test test-unit test-e2e fmt \
        tf-init tf-validate tf-plan tf-apply tf-destroy \
        localstack-up localstack-down e2e-localstack \
        deploy-static clean

TF := terraform -chdir=infrastructure/terraform

install:  ## Create venv and sync dev deps via uv
	uv sync --extra dev

dev:  ## Run the FastAPI local server with hot reload
	uv run uvicorn backend.local.server:app --reload --port $${PORT:-8000}

test:  ## Run the full pytest suite (unit + WS e2e + LocalStack e2e if available)
	uv run pytest -q

test-unit:  ## Run only the unit tests (skip e2e)
	uv run pytest -q tests/test_state.py tests/test_auth.py tests/test_broadcaster.py tests/test_storage_dynamodb.py

test-e2e:  ## Run only the e2e tests (LocalStack + FastAPI)
	uv run pytest -q tests/test_e2e_local.py tests/test_e2e_terraform_localstack.py

# ── Terraform ────────────────────────────────────────────────────────
tf-init:  ## terraform init
	$(TF) init -input=false

tf-validate:  ## terraform validate
	$(TF) validate

tf-plan:  ## terraform plan against AWS
	$(TF) plan -var "api_key=$${SLIDES_API_KEY:-changeme-rotate-me}"

tf-apply:  ## terraform apply against AWS
	$(TF) apply -var "api_key=$${SLIDES_API_KEY:-changeme-rotate-me}"

tf-destroy:  ## terraform destroy against AWS
	$(TF) destroy -var "api_key=$${SLIDES_API_KEY:-changeme-rotate-me}"

# ── LocalStack ────────────────────────────────────────────────────────
localstack-up:  ## Boot LocalStack
	docker compose -f infrastructure/localstack/docker-compose.yml up -d
	@./infrastructure/localstack/bootstrap.sh || true

localstack-down:  ## Stop LocalStack and wipe its volume
	docker compose -f infrastructure/localstack/docker-compose.yml down -v

tf-localstack-init:  ## terraform init for LocalStack
	$(TF) init -input=false

tf-localstack-apply:  ## terraform apply the slim stack to LocalStack
	$(TF) apply -var-file=localstack.tfvars -auto-approve -input=false

tf-localstack-destroy:  ## terraform destroy the LocalStack stack
	$(TF) destroy -var-file=localstack.tfvars -auto-approve -input=false

e2e-localstack: localstack-up tf-localstack-apply  ## Full local e2e: up + apply + test
	uv run pytest -q tests/test_e2e_terraform_localstack.py

# ── Static asset sync ────────────────────────────────────────────────
deploy-static:  ## Sync ../docs/showcase-pro to the S3 bucket from Terraform outputs
	@BUCKET=$$($(TF) output -raw static_bucket 2>/dev/null); \
	if [ -z "$$BUCKET" ]; then echo "static bucket not deployed"; exit 1; fi; \
	aws s3 sync ../docs/showcase-pro/ s3://$$BUCKET/showcase/ --exclude "*.mp4"

clean:
	rm -rf .pytest_cache **/__pycache__ infrastructure/terraform/build infrastructure/terraform/.terraform
