# Bootstrap: the account-level foundation. Uses local state (git-ignored), because the
# state bucket it creates is where the stack keeps its own state.

data "aws_caller_identity" "current" {}

locals {
  tags = {
    app         = "dealpulse"
    env         = "demo"
    managed_by  = "terraform"
    name_prefix = var.name_prefix
  }
  # Bucket names are global; the account ID keeps this one unique.
  state_bucket = "${var.name_prefix}-tfstate-${data.aws_caller_identity.current.account_id}"
}

# ------------------------------------------------------------ Terraform state bucket

resource "aws_s3_bucket" "tf_state" {
  bucket        = local.state_bucket
  force_destroy = var.state_bucket_force_destroy
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Keep old state versions for 90 days; they're the undo history for the stack.
resource "aws_s3_bucket_lifecycle_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# Refuse any request that isn't over TLS.
resource "aws_s3_bucket_policy" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.tf_state.arn, "${aws_s3_bucket.tf_state.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.tf_state]
}
