# IAC-03: service identities and least-privilege IAM. No keys are ever created.
#
#   weekendwise-run     Cloud Run runtime: call Vertex AI, READ Firestore, write logs
#   weekendwise-ingest  `make seed`: call Vertex AI (embeddings), read/WRITE Firestore
#   weekendwise-build   Cloud Build: push images, write logs, read uploaded source
#
# Role choices (checked against Google's predefined roles, 2026-11-06):
#   roles/aiplatform.user        Smallest predefined role that can call Gemini and embedding
#                                models. Broader than invoke-only; a custom role was avoided
#                                because deleted custom-role IDs can't be reused for ~37 days,
#                                which breaks destroy/rebuild cycles.
#   roles/datastore.viewer       Read-only Firestore (runtime must not write).
#   roles/datastore.user         Read/write Firestore documents (ingestion only).
#   roles/logging.logWriter      Write logs.
#   roles/artifactregistry.writer  Push images (build only).
#   roles/storage.objectViewer   Read the source archive Cloud Build uploads (build only).

locals {
  service_accounts = {
    run = {
      account_id  = "weekendwise-run"
      name        = "WeekendWise Cloud Run runtime"
      description = "Attached to Cloud Run. Calls Vertex AI and reads Firestore. Managed by Terraform."
      roles       = ["roles/aiplatform.user", "roles/datastore.viewer", "roles/logging.logWriter"]
    }
    ingest = {
      account_id  = "weekendwise-ingest"
      name        = "WeekendWise corpus ingestion"
      description = "Used by make seed via impersonation. Embeds and writes guide chunks. Managed by Terraform."
      roles       = ["roles/aiplatform.user", "roles/datastore.user"]
    }
    build = {
      account_id  = "weekendwise-build"
      name        = "WeekendWise Cloud Build"
      description = "Runs container builds and pushes images. Managed by Terraform."
      roles       = ["roles/artifactregistry.writer", "roles/logging.logWriter", "roles/storage.objectViewer"]
    }
  }

  project_role_bindings = merge([
    for key, sa in local.service_accounts : {
      for role in sa.roles : "${key}:${role}" => { sa = key, role = role }
    }
  ]...)

  # Operators may impersonate every account (to run make seed / builds and to test
  # the runtime identity's access in make verify) and act as run/build when deploying.
  operator_token_creator = merge([
    for p in var.operator_principals : {
      for key in keys(local.service_accounts) : "${key}:${p}" => { sa = key, member = p }
    }
  ]...)
  operator_act_as = merge([
    for p in var.operator_principals : {
      for key in ["run", "build"] : "${key}:${p}" => { sa = key, member = p }
    }
  ]...)
}

resource "google_service_account" "this" {
  for_each = local.service_accounts

  project      = var.project_id
  account_id   = each.value.account_id
  display_name = each.value.name
  description  = each.value.description
}

# Additive bindings only (_member), so Terraform never removes unrelated access.
resource "google_project_iam_member" "service_account_roles" {
  for_each = local.project_role_bindings

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.this[each.value.sa].email}"
}

resource "google_service_account_iam_member" "operator_token_creator" {
  for_each = local.operator_token_creator

  service_account_id = google_service_account.this[each.value.sa].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value.member
}

resource "google_service_account_iam_member" "operator_act_as" {
  for_each = local.operator_act_as

  service_account_id = google_service_account.this[each.value.sa].name
  role               = "roles/iam.serviceAccountUser"
  member             = each.value.member
}
