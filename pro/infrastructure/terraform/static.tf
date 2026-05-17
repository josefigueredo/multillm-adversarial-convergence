# ── Static hosting ────────────────────────────────────────────────────
# Gated on var.deploy_static so we can skip CloudFront on LocalStack
# Community (which lacks CloudFront support).

resource "random_id" "bucket_suffix" {
  count       = var.deploy_static ? 1 : 0
  byte_length = 4
}

resource "aws_s3_bucket" "static" {
  count         = var.deploy_static ? 1 : 0
  bucket        = "${local.resource_prefix}-${random_id.bucket_suffix[0].hex}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "static" {
  count  = var.deploy_static ? 1 : 0
  bucket = aws_s3_bucket.static[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "static" {
  count                   = var.deploy_static ? 1 : 0
  bucket                  = aws_s3_bucket.static[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront origin access control (OAC) — modern replacement for OAI.
resource "aws_cloudfront_origin_access_control" "static" {
  count                             = var.deploy_static ? 1 : 0
  name                              = "${local.resource_prefix}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "static" {
  count               = var.deploy_static ? 1 : 0
  enabled             = true
  default_root_object = "showcase/index.html"
  price_class         = "PriceClass_100" # NA + EU; cheaper than All

  origin {
    domain_name              = aws_s3_bucket.static[0].bucket_regional_domain_name
    origin_id                = "s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.static[0].id
  }

  default_cache_behavior {
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# CloudFront → S3 (OAC) policy
data "aws_iam_policy_document" "static_bucket" {
  count = var.deploy_static ? 1 : 0

  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.static[0].arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.static[0].arn]
    }
  }
}

resource "aws_s3_bucket_policy" "static" {
  count  = var.deploy_static ? 1 : 0
  bucket = aws_s3_bucket.static[0].id
  policy = data.aws_iam_policy_document.static_bucket[0].json
}
