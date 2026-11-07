output "project_id" {
  value = data.google_project.this.project_id
}

output "project_number" {
  value = data.google_project.this.number
}

output "service_accounts" {
  description = "Service account emails by purpose."
  value       = { for key, sa in google_service_account.this : key => sa.email }
}

output "firestore" {
  description = "Values the app needs (FIRESTORE_DATABASE_ID, FIRESTORE_COLLECTION, VERTEX_EMBEDDING_DIMENSION)."
  value = {
    database            = google_firestore_database.default.name
    location            = google_firestore_database.default.location_id
    collection          = google_firestore_index.guide_chunks_vector.collection
    vector_field        = "embedding"
    embedding_dimension = var.embedding_dimension
    vector_index        = google_firestore_index.guide_chunks_vector.name
    delete_protection   = google_firestore_database.default.delete_protection_state
  }
}

output "cloud_run" {
  description = "Cloud Run service details (IAC-05)."
  value = {
    name                  = google_cloud_run_v2_service.app.name
    url                   = google_cloud_run_v2_service.app.uri
    image                 = var.image
    service_account       = google_cloud_run_v2_service.app.template[0].service_account
    min_instances         = google_cloud_run_v2_service.app.template[0].scaling[0].min_instance_count
    max_instances         = google_cloud_run_v2_service.app.template[0].scaling[0].max_instance_count
    public                = var.allow_unauthenticated
    deletion_protection   = google_cloud_run_v2_service.app.deletion_protection
    latest_ready_revision = google_cloud_run_v2_service.app.latest_ready_revision
  }
}

output "image_repository" {
  description = "Where `make build` pushes images (append :<tag>)."
  value       = local.image_repository
}
