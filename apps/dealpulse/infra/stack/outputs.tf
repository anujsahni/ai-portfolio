output "name_prefix" {
  value = var.name_prefix
}

output "region" {
  value = var.region
}

output "names" {
  description = "Fixed resource names used across the stack and the app."
  value       = local.names
}

output "models" {
  value = {
    claude_model_id          = var.claude_model_id
    claude_inference_profile = var.claude_inference_profile
    titan_model_id           = var.titan_model_id
  }
}

output "network" {
  value = {
    vpc_id            = aws_vpc.main.id
    public_subnet_ids = aws_subnet.public[*].id
    app_sg_id         = aws_security_group.app.id
  }
}

output "roles" {
  description = "IAM role ARNs by purpose."
  value = {
    run       = aws_iam_role.run.arn
    ingest    = aws_iam_role.ingest.arn
    training  = aws_iam_role.training.arn
    build     = aws_iam_role.build.arn
    task_exec = aws_iam_role.task_exec.arn
  }
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}

output "opensearch" {
  value = {
    domain          = aws_opensearch_domain.main.domain_name
    endpoint        = aws_opensearch_domain.main.endpoint
    engine_version  = aws_opensearch_domain.main.engine_version
    instance_type   = var.opensearch_instance_type
    index           = local.names.index
    search_pipeline = "${local.names.index}-hybrid"
  }
}

output "guardrail" {
  value = {
    id      = aws_bedrock_guardrail.main.guardrail_id
    arn     = aws_bedrock_guardrail.main.guardrail_arn
    version = aws_bedrock_guardrail_version.main.version
  }
}

output "model" {
  value = {
    package_group    = aws_sagemaker_model_package_group.win_model.model_package_group_name
    deployed_package = var.model_package_arn
    endpoint         = local.deploy_model ? aws_sagemaker_endpoint.win_model[0].name : null
    memory_mb        = var.endpoint_memory_mb
    max_concurrency  = var.endpoint_max_concurrency
  }
}
