# ------------------------------------------------------------ SageMaker registry and endpoint (IAC-05)
#
# The registry (model package group) always exists. The serverless endpoint exists only once an
# *approved* model version is chosen: `make deploy-model MODEL=<package-arn>` writes
# model.auto.tfvars.json and applies. Rolling back means deploying the previous approved ARN.
# Serverless Inference scales to zero; you pay per request (a cold start can take a few seconds).

resource "aws_sagemaker_model_package_group" "win_model" {
  model_package_group_name        = "${var.name_prefix}-win-model"
  model_package_group_description = "DealPulse win-probability model versions (XGBoost), with evaluation metrics and approval status"
}

locals {
  deploy_model = var.model_package_arn != ""
  # Serverless runs the container as non-root, so its startup `pip install` of inference.py
  # can't write to /opt/venv. Install into /tmp and import from there. Set here as well as in
  # scripts/train_model.py so model versions registered before that fix still deploy.
  model_env = { PIP_TARGET = "/tmp", PYTHONPATH = "/tmp" }
  # A new model version (or container settings) needs a new model and endpoint configuration;
  # the endpoint switches over.
  model_suffix = substr(sha1("${var.model_package_arn}${jsonencode(local.model_env)}"), 0, 8)
}

resource "aws_sagemaker_model" "win_model" {
  count              = local.deploy_model ? 1 : 0
  name               = "${var.name_prefix}-win-model-${local.model_suffix}"
  execution_role_arn = aws_iam_role.training.arn

  primary_container {
    model_package_name = var.model_package_arn
    environment        = local.model_env
  }
}

resource "aws_sagemaker_endpoint_configuration" "win_model" {
  count = local.deploy_model ? 1 : 0
  name  = "${var.name_prefix}-win-model-${local.model_suffix}"

  production_variants {
    variant_name = "AllTraffic"
    model_name   = aws_sagemaker_model.win_model[0].name

    serverless_config {
      memory_size_in_mb = var.endpoint_memory_mb
      max_concurrency   = var.endpoint_max_concurrency
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_sagemaker_endpoint" "win_model" {
  count                = local.deploy_model ? 1 : 0
  name                 = local.names.endpoint
  endpoint_config_name = aws_sagemaker_endpoint_configuration.win_model[0].name
}
