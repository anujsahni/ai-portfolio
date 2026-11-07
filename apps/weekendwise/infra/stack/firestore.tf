# IAC-04: Firestore (default) database and the vector index used by retrieval (MVP-05).
#
# Retrieval query (MVP-05): collection guide_chunks, where cityId == X and active == true,
# nearest neighbours on `embedding`. That needs a composite index of
# cityId ASC + active ASC + embedding (vector, flat).
#
# Terraform never writes documents; `make seed` (MVP-04) loads data as weekendwise-ingest.

locals {
  firestore_location = coalesce(var.firestore_location, var.region)
}

resource "google_firestore_database" "default" {
  project          = var.project_id
  name             = "(default)" # eligible for Firestore's free daily quota
  location_id      = local.firestore_location
  type             = "FIRESTORE_NATIVE"
  database_edition = "STANDARD"

  # Protection is ON by default. `make destroy` / `make destroy-all` switch it off just before deleting.
  delete_protection_state = var.firestore_delete_protection ? "DELETE_PROTECTION_ENABLED" : "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE" # really delete on destroy (provider default would only forget it)
}

resource "google_firestore_index" "guide_chunks_vector" {
  project     = var.project_id
  database    = google_firestore_database.default.name
  collection  = "guide_chunks"
  query_scope = "COLLECTION"

  fields {
    field_path = "cityId"
    order      = "ASCENDING"
  }

  fields {
    field_path = "active"
    order      = "ASCENDING"
  }

  # Firestore always inserts the document ID before the vector field. Declaring it here
  # matches what Google stores; without it every plan would try to rebuild the index.
  fields {
    field_path = "__name__"
    order      = "ASCENDING"
  }

  fields {
    field_path = "embedding"
    vector_config {
      dimension = var.embedding_dimension
      flat {}
    }
  }

  deletion_policy = "DELETE"
}
