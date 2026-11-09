# Stack: everything the app needs. Resources are added story by story:
#   network.tf, iam.tf (IAC-03) · s3.tf, opensearch.tf (IAC-04) · sagemaker.tf, bedrock.tf (IAC-05)
#   ecr.tf, codebuild.tf, ecs.tf (IAC-06)

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  # Who may assume the run and ingest roles: the identity running Terraform, unless overridden.
  operator_arns = length(var.operator_arns) > 0 ? var.operator_arns : [data.aws_caller_identity.current.arn]

  # Fixed names for resources created by later stories, so IAM can be scoped to them today.
  names = {
    bucket        = "${var.name_prefix}-data-${local.account_id}"
    domain        = var.name_prefix # OpenSearch domain names: 3–28 lowercase chars
    index         = "deal_passages"
    endpoint      = "${var.name_prefix}-win-model"
    ecr_repo      = var.name_prefix
    app_log_group = "/${var.name_prefix}/app"
  }

  arn = {
    bucket        = "arn:${local.partition}:s3:::${local.names.bucket}"
    domain        = "arn:${local.partition}:es:${var.region}:${local.account_id}:domain/${local.names.domain}"
    endpoint      = "arn:${local.partition}:sagemaker:${var.region}:${local.account_id}:endpoint/${local.names.endpoint}"
    ecr_repo      = "arn:${local.partition}:ecr:${var.region}:${local.account_id}:repository/${local.names.ecr_repo}"
    app_log_group = "arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:${local.names.app_log_group}"
    titan         = "arn:${local.partition}:bedrock:${var.region}::foundation-model/${var.titan_model_id}"
    # Claude is called through a US cross-region inference profile. Callers need the profile and
    # the model in every region the profile can route to.
    claude = [
      "arn:${local.partition}:bedrock:${var.region}:${local.account_id}:inference-profile/${var.claude_inference_profile}",
      "arn:${local.partition}:bedrock:*::foundation-model/${var.claude_model_id}",
    ]
  }
}
