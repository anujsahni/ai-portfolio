# ------------------------------------------------------------ IAM roles (IAC-03)
#
# Five roles, each limited to named resources. Resources from later stories (bucket, OpenSearch
# domain, endpoint, ECR repository, log groups) are referenced by their fixed names in locals,
# so permissions are scoped now and can be checked with the IAM policy simulator (make verify).
# There are no IAM users and no access keys. Operators assume run/ingest for local work.

data "aws_iam_policy_document" "operator_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:PrincipalArn"
      values   = local.operator_arns
    }
  }
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# ---------------------------------------------------------------- run: the app

data "aws_iam_policy_document" "run_trust" {
  source_policy_documents = [
    data.aws_iam_policy_document.ecs_tasks_assume.json,
    data.aws_iam_policy_document.operator_assume.json, # make run / smoke tests locally as the app
  ]
}

resource "aws_iam_role" "run" {
  name                 = "${var.name_prefix}-run"
  description          = "DealPulse app (ECS task role; operators assume it for local runs)"
  assume_role_policy   = data.aws_iam_policy_document.run_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "run" {
  statement {
    sid       = "ScoreDeals"
    actions   = ["sagemaker:InvokeEndpoint"]
    resources = [local.arn.endpoint]
  }
  statement {
    sid       = "ClaudeAndTitan"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = concat(local.arn.claude, [local.arn.titan])
  }
  statement {
    sid       = "Guardrail"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [aws_bedrock_guardrail.main.guardrail_arn]
  }
  statement {
    sid       = "SearchOnly"
    actions   = ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpHead"]
    resources = ["${local.arn.domain}/${local.names.index}/_search"]
  }
  statement {
    sid       = "ReadSnapshotAndReports"
    actions   = ["s3:GetObject"]
    resources = ["${local.arn.bucket}/crm-snapshot/*", "${local.arn.bucket}/reports/*"]
  }
  statement {
    sid       = "ListSnapshotAndReports"
    actions   = ["s3:ListBucket"]
    resources = [local.arn.bucket]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["crm-snapshot/*", "reports/*"]
    }
  }
  statement {
    sid       = "AppLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.arn.app_log_group}:*"]
  }
  statement {
    sid = "EcsExecForProxy"
    # ECS Exec / SSM port forwarding (make proxy). These actions don't support resource scoping.
    actions = [
      "ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "run" {
  name   = "dealpulse-run"
  role   = aws_iam_role.run.id
  policy = data.aws_iam_policy_document.run.json
}

# ---------------------------------------------------------------- ingest: make seed

resource "aws_iam_role" "ingest" {
  name                 = "${var.name_prefix}-ingest"
  description          = "DealPulse knowledge-base loader (make seed); the only writer of the OpenSearch index"
  assume_role_policy   = data.aws_iam_policy_document.operator_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "ingest" {
  statement {
    sid       = "EmbedOnly"
    actions   = ["bedrock:InvokeModel"]
    resources = [local.arn.titan]
  }
  statement {
    sid       = "IndexReadWrite"
    actions   = ["es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPost", "es:ESHttpPut", "es:ESHttpDelete"]
    resources = ["${local.arn.domain}/*"]
  }
  statement {
    sid       = "ReadSources"
    actions   = ["s3:GetObject"]
    resources = ["${local.arn.bucket}/crm-snapshot/*", "${local.arn.bucket}/knowledge/*"]
  }
  statement {
    sid       = "ListSources"
    actions   = ["s3:ListBucket"]
    resources = [local.arn.bucket]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["crm-snapshot/*", "knowledge/*"]
    }
  }
}

resource "aws_iam_role_policy" "ingest" {
  name   = "dealpulse-ingest"
  role   = aws_iam_role.ingest.id
  policy = data.aws_iam_policy_document.ingest.json
}

# ---------------------------------------------------------------- training: SageMaker jobs and model hosting

resource "aws_iam_role" "training" {
  name        = "${var.name_prefix}-training"
  description = "DealPulse SageMaker training jobs and the serverless model's execution role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

data "aws_iam_policy_document" "training" {
  statement {
    sid       = "ReadTrainingDataAndModels"
    actions   = ["s3:GetObject"]
    resources = ["${local.arn.bucket}/training/*", "${local.arn.bucket}/models/*"]
  }
  statement {
    sid       = "WriteModels"
    actions   = ["s3:PutObject"]
    resources = ["${local.arn.bucket}/models/*"]
  }
  statement {
    sid       = "ListTrainingAndModels"
    actions   = ["s3:ListBucket"]
    resources = [local.arn.bucket]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["training/*", "models/*"]
    }
  }
  statement {
    sid       = "SageMakerLogs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/sagemaker/*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"] # PutMetricData has no resource-level permissions
    condition {
      test     = "StringLike"
      variable = "cloudwatch:namespace"
      values   = ["/aws/sagemaker/*", "aws/sagemaker/*"]
    }
  }
  statement {
    sid = "PullAwsContainers"
    # SageMaker's managed XGBoost image lives in an AWS-owned ECR registry.
    actions   = ["ecr:GetAuthorizationToken", "ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "training" {
  name   = "dealpulse-training"
  role   = aws_iam_role.training.id
  policy = data.aws_iam_policy_document.training.json
}

# ---------------------------------------------------------------- build: CodeBuild

resource "aws_iam_role" "build" {
  name        = "${var.name_prefix}-build"
  description = "DealPulse CodeBuild: tests, builds and pushes the app image"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

data "aws_iam_policy_document" "build" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # account-level action
  }
  statement {
    sid = "PushAppImage"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage",
    ]
    resources = [local.arn.ecr_repo]
  }
  statement {
    sid       = "ReadSourceUpload"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${local.arn.bucket}/build-src/*"]
  }
  statement {
    sid       = "BuildLogs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/codebuild/${var.name_prefix}*"]
  }
}

resource "aws_iam_role_policy" "build" {
  name   = "dealpulse-build"
  role   = aws_iam_role.build.id
  policy = data.aws_iam_policy_document.build.json
}

# ---------------------------------------------------------------- task-exec: ECS agent

resource "aws_iam_role" "task_exec" {
  name               = "${var.name_prefix}-task-exec"
  description        = "ECS agent for DealPulse: pull the image, create the log stream"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task_exec" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "PullAppImage"
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
    resources = [local.arn.ecr_repo]
  }
  statement {
    sid       = "AppLogStream"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.arn.app_log_group}:*"]
  }
}

resource "aws_iam_role_policy" "task_exec" {
  name   = "dealpulse-task-exec"
  role   = aws_iam_role.task_exec.id
  policy = data.aws_iam_policy_document.task_exec.json
}
