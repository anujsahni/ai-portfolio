terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.10"
    }
  }

  # Bucket and prefix come from backend.hcl, written by `make bootstrap`.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
