# IAC-05: the Cloud Run service. Scale to zero, bounded max instances, dedicated runtime identity, no secrets.

resource "google_cloud_run_v2_service" "app" {
  project             = var.project_id
  name                = "weekendwise"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.cloud_run_deletion_protection
  description         = "WeekendWise demo app. Managed by Terraform (make deploy)."

  template {
    service_account                  = google_service_account.this["run"].email
    timeout                          = "180s" # planner stops itself at 150 s
    max_instance_request_concurrency = 10

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true # CPU only while handling requests
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = merge(var.app_env, {
          GCP_PROJECT_ID             = var.project_id
          GCP_REGION                 = var.region
          VERTEX_EMBEDDING_LOCATION  = var.region
          VERTEX_EMBEDDING_DIMENSION = tostring(var.embedding_dimension)
          FIRESTORE_DATABASE_ID      = google_firestore_database.default.name
          FIRESTORE_COLLECTION       = google_firestore_index.guide_chunks_vector.collection
          APP_VERSION                = element(split(":", var.image), length(split(":", var.image)) - 1)
        })
        content {
          name  = env.key
          value = env.value
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 0
        period_seconds        = 3
        failure_threshold     = 10
        timeout_seconds       = 2
      }
    }
  }

  # The runtime identity needs its roles before the first revision starts.
  depends_on = [google_project_iam_member.service_account_roles]
}

# Private by default: only operators may invoke (e.g. through `make proxy`). Public only when allow_unauthenticated = true.
resource "google_cloud_run_v2_service_iam_member" "operator_invoker" {
  for_each = toset(var.operator_principals)

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = each.value
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
