# name_prefix and region come from bootstrap.auto.tfvars.json, written by `make bootstrap`.

variable "name_prefix" {
  description = "Unique prefix for resource names (from bootstrap)."
  type        = string
}

variable "region" {
  description = "AWS region (from bootstrap)."
  type        = string
}

variable "operator_arns" {
  description = "IAM principals allowed to assume the run and ingest roles. Empty = whoever runs Terraform."
  type        = list(string)
  default     = []
}

variable "claude_model_id" {
  description = "Bedrock model ID for Claude."
  type        = string
  default     = "anthropic.claude-opus-5-5"
}

variable "claude_inference_profile" {
  description = "Cross-region inference profile used to call Claude (the model has no on-demand access in-region)."
  type        = string
  default     = "us.anthropic.claude-opus-5-5"
}

variable "titan_model_id" {
  description = "Bedrock model ID for embeddings."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "data_bucket_force_destroy" {
  description = "Allow deleting the data bucket with objects in it. Only make destroy sets this to true."
  type        = bool
  default     = false
}

variable "opensearch_engine_version" {
  description = "OpenSearch engine version for the domain."
  type        = string
  default     = "OpenSearch_3.7"
}

variable "opensearch_instance_type" {
  description = "Single data node type. t3.small.search is the cheapest that supports vector search (~$0.036/hour)."
  type        = string
  default     = "t3.small.search"
}

variable "model_package_arn" {
  description = "Approved SageMaker model package to serve. Empty = no endpoint. Set by make deploy-model (model.auto.tfvars.json)."
  type        = string
  default     = ""
}

variable "endpoint_memory_mb" {
  description = "Serverless endpoint memory (1024–6144 in 1 GB steps)."
  type        = number
  default     = 2048
}

variable "endpoint_max_concurrency" {
  description = "Serverless endpoint: most requests handled at once."
  type        = number
  default     = 2
}
