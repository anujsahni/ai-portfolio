terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }

  # Bucket, key, region and locking come from backend.hcl, written by `make bootstrap`.
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      app         = "dealpulse"
      env         = "demo"
      managed_by  = "terraform"
      name_prefix = var.name_prefix
    }
  }
}
