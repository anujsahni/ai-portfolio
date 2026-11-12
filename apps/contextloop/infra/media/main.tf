# ContextLoop media: a private S3 bucket served through CloudFront, for the narrated pitch video and its public watch page.
#
#   make media-infra     creates this stack (once)
#   make publish-pitch   uploads the latest render and refreshes CloudFront
#
# The bucket is never public: Block Public Access is on and only this CloudFront distribution can read it (origin access
# control). Anyone with the CloudFront link can watch the video, so publish only demo content (ContextLoop's data is synthetic).
# State is local (infra/media/terraform.tfstate, git-ignored): this stack is small and holds no secrets.

terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { app = "contextloop", env = "demo", managed_by = "terraform", purpose = "pitch-video" }
  }
}

data "aws_caller_identity" "me" {}

locals {
  bucket = "contextloop-media-${data.aws_caller_identity.me.account_id}"
}

# ---------------------------------------------------------------------------------------------------------------- bucket
resource "aws_s3_bucket" "media" {
  bucket        = local.bucket
  force_destroy = true # media is re-uploadable from a local render; lets `terraform destroy` clean up fully
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ------------------------------------------------------------------------------------------------------------ CloudFront
resource "aws_cloudfront_origin_access_control" "media" {
  name                              = "${local.bucket}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_response_headers_policy" "cors" {
  name = "Managed-SimpleCORS" # lets the app on another origin play the video and load its captions
}

resource "aws_cloudfront_distribution" "media" {
  enabled             = true
  comment             = "ContextLoop pitch video"
  price_class         = "PriceClass_100" # North America and Europe edge locations: the cheapest class
  http_version        = "http2and3"
  default_root_object = "pitch/index.html"

  origin {
    origin_id                = "media"
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.media.id
  }

  default_cache_behavior {
    target_origin_id           = "media"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.cors.id
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

# Only this distribution may read the bucket.
resource "aws_s3_bucket_policy" "media" {
  bucket     = aws_s3_bucket.media.id
  depends_on = [aws_s3_bucket_public_access_block.media]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "CloudFrontReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.media.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.media.arn } }
    }]
  })
}

# --------------------------------------------------------------------------------------------------------------- outputs
output "bucket" {
  value = aws_s3_bucket.media.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.media.id
}

output "base_url" {
  value = "https://${aws_cloudfront_distribution.media.domain_name}"
}
