# ------------------------------------------------------------ Data bucket (IAC-04)
#
# One bucket, organised by prefix:
#   crm-snapshot/  synthetic Salesforce records the app reads        (MVP-03)
#   training/      point-in-time training rows                        (MVP-03, MVP-04)
#   knowledge/     playbook, policy and win/loss documents            (MVP-03, MVP-06)
#   models/        SageMaker training output                          (MVP-04)
#   reports/       evaluation reports shown on the Model page         (MVP-04, MVP-11)
#   build-src/     source uploads for CodeBuild                       (IAC-06)

resource "aws_s3_bucket" "data" {
  bucket        = local.names.bucket
  force_destroy = var.data_bucket_force_destroy
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
  rule {
    id     = "expire-build-uploads"
    status = "Enabled"
    filter {
      prefix = "build-src/"
    }
    expiration {
      days = 14
    }
  }
}

resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.data]
}
