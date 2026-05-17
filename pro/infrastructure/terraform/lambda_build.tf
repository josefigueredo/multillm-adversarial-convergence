# ── Build pipeline ────────────────────────────────────────────────────
# We bundle the source AND third-party deps (pydantic) into a single zip
# per function. Lambda Layers would save a few MB, but LocalStack has
# known quirks with layered imports — and pydantic compressed is ~2.5MB,
# so the cost is invisible. Same build artifact for AWS and LocalStack.
#
#   build/code/
#     handlers/                <- our source
#     shared/                  <- our source
#     pydantic/                <- pip-installed
#     pydantic_core/
#     ...

locals {
  repo_root = "${path.module}/../.."

  build_dir      = "${path.module}/build"
  code_stage_dir = "${path.module}/build/code"
  code_zip       = "${path.module}/build/code.zip"

  # Trigger a rebuild when any backend file or the requirements file changes.
  source_hash = sha1(join("", [
    for f in fileset("${local.repo_root}/backend", "{shared,handlers}/**/*.py") :
    filesha1("${local.repo_root}/backend/${f}")
  ]))
}

resource "null_resource" "build_code" {
  triggers = {
    source_hash       = local.source_hash
    requirements_hash = filesha1("${local.repo_root}/backend/requirements.txt")
    arch              = var.lambda_architecture
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      rm -rf "${local.code_stage_dir}"
      mkdir -p "${local.code_stage_dir}"

      # 1. Source code
      cp -R "${local.repo_root}/backend/handlers" "${local.code_stage_dir}/handlers"
      cp -R "${local.repo_root}/backend/shared"   "${local.code_stage_dir}/shared"

      # 2. Dependencies — pinned to the Lambda runtime ABI
      PLATFORM=${var.lambda_architecture == "arm64" ? "manylinux2014_aarch64" : "manylinux2014_x86_64"}
      PYTHON=$(command -v python3.12 || command -v python3 || command -v python)
      "$PYTHON" -m pip install --quiet \
        --target "${local.code_stage_dir}" \
        --platform "$PLATFORM" \
        --implementation cp \
        --python-version 3.12 \
        --only-binary=:all: \
        -r "${local.repo_root}/backend/requirements.txt"

      # 3. Strip noise
      find "${local.code_stage_dir}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
      find "${local.code_stage_dir}" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    EOT
  }
}

data "archive_file" "code" {
  depends_on  = [null_resource.build_code]
  type        = "zip"
  source_dir  = local.code_stage_dir
  output_path = local.code_zip
}
