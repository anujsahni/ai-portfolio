# IAC-05: private Docker repository for the app image. Images are pushed by `make build` as weekendwise-build.

resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = "weekendwise"
  format        = "DOCKER"
  description   = "WeekendWise app images. Managed by Terraform."

  cleanup_policy_dry_run = false

  # Keep the most recent images (rollback targets); delete anything older than 30 days that isn't among them.
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.registry_keep_count
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "2592000s"
    }
  }
}

locals {
  image_repository = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}/app"
}
