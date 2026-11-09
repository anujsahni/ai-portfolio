# ------------------------------------------------------------ OpenSearch domain (IAC-04)
#
# One small node: the cheapest real OpenSearch with vector and hybrid search (~$0.036/hour,
# billed even when idle). Public endpoint, but every request must be signed by an allowed IAM
# role; there is no anonymous access and no fine-grained internal users.
#
# Within one account, a domain's access policy can grant access on its own, even where a role's
# IAM policy doesn't. So this policy repeats each role's limits instead of granting domain/*.

resource "aws_cloudwatch_log_group" "opensearch_errors" {
  name              = "/aws/opensearch/${var.name_prefix}/errors"
  retention_in_days = 14
}

data "aws_iam_policy_document" "opensearch_logs" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.opensearch_errors.arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["es.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name     = "${var.name_prefix}-opensearch-logs"
  policy_document = data.aws_iam_policy_document.opensearch_logs.json
}

data "aws_iam_policy_document" "opensearch_access" {
  statement {
    sid     = "AppSearchOnly"
    actions = ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpHead"]
    principals {
      type        = "AWS"
      identifiers = [aws_iam_role.run.arn]
    }
    resources = ["${local.arn.domain}/${local.names.index}/_search"]
  }
  statement {
    sid     = "IngestAndOperatorReadWrite"
    actions = ["es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPost", "es:ESHttpPut", "es:ESHttpDelete"]
    principals {
      type        = "AWS"
      identifiers = concat([aws_iam_role.ingest.arn], local.operator_arns)
    }
    resources = ["${local.arn.domain}/*"]
  }
}

resource "aws_opensearch_domain" "main" {
  domain_name    = local.names.domain
  engine_version = var.opensearch_engine_version

  cluster_config {
    instance_type          = var.opensearch_instance_type
    instance_count         = 1
    zone_awareness_enabled = false
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = 10
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-PFS-2023-10"
  }

  advanced_security_options {
    enabled = false # IAM-only access; no internal users
  }

  software_update_options {
    auto_software_update_enabled = false
  }

  log_publishing_options {
    log_type                 = "ES_APPLICATION_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_errors.arn
  }

  access_policies = data.aws_iam_policy_document.opensearch_access.json

  depends_on = [aws_cloudwatch_log_resource_policy.opensearch]
}
