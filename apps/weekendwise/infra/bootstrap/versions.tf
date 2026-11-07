terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.10"
    }
  }
}

# Default provider: creates the project and resources inside it.
provider "google" {
  region = var.region
}

# The Budget API needs a quota project when called with user credentials.
# This alias bills those calls to the new project (where the API is enabled).
provider "google" {
  alias                 = "billing"
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}
