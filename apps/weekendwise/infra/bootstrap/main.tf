locals {
  labels = {
    app        = "weekendwise"
    managed-by = "terraform"
  }

  # APIs the MVP uses, plus the APIs Terraform needs to manage the project.
  mvp_services = [
    "aiplatform.googleapis.com",       # Vertex AI (Gemini + embeddings)
    "firestore.googleapis.com",        # Firestore
    "run.googleapis.com",              # Cloud Run
    "cloudbuild.googleapis.com",       # Cloud Build
    "artifactregistry.googleapis.com", # Artifact Registry
    "logging.googleapis.com",          # Cloud Logging
  ]
  terraform_services = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "iam.googleapis.com",
    "billingbudgets.googleapis.com",
    "storage.googleapis.com", # Terraform state bucket
  ]
  alert_services = length(var.alert_emails) > 0 ? ["monitoring.googleapis.com"] : []

  services = toset(concat(local.mvp_services, local.terraform_services, local.alert_services))

  budget_thresholds = [0.5, 0.8, 1.0]
}

# ---------------------------------------------------------------- project

resource "google_project" "this" {
  name            = var.project_name
  project_id      = var.project_id
  org_id          = var.org_id
  folder_id       = var.folder_id
  billing_account = var.billing_account_id
  labels          = local.labels
  deletion_policy = var.project_deletion_policy
}

resource "google_project_service" "enabled" {
  for_each = local.services

  project = google_project.this.project_id
  service = each.value

  # The project itself is deleted on full teardown, so don't disable APIs one by one.
  disable_on_destroy         = false
  disable_dependent_services = false
}

# ---------------------------------------------------------------- budget ($20/month max)

resource "google_monitoring_notification_channel" "budget_email" {
  for_each = toset(var.alert_emails)

  project      = google_project.this.project_id
  display_name = "WeekendWise budget alert: ${each.value}"
  type         = "email"
  labels = {
    email_address = each.value
  }

  depends_on = [google_project_service.enabled]
}

resource "google_billing_budget" "monthly" {
  provider = google.billing

  billing_account = var.billing_account_id
  display_name    = "weekendwise-monthly-${var.budget_amount_usd}${lower(var.budget_currency)}"

  budget_filter {
    projects               = ["projects/${google_project.this.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "EXCLUDE_ALL_CREDITS" # alert on real usage even if credits pay for it
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(floor(var.budget_amount_usd))
    }
  }

  dynamic "threshold_rules" {
    for_each = local.budget_thresholds
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }

  # Early warning when the month is forecast to exceed the budget.
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  # Billing admins/users are emailed by default. Only add this block when extra
  # recipients are set: Google drops an empty one, which would show as drift on every plan.
  dynamic "all_updates_rule" {
    for_each = length(var.alert_emails) > 0 ? [1] : []
    content {
      monitoring_notification_channels = [for c in google_monitoring_notification_channel.budget_email : c.id]
      disable_default_iam_recipients   = false
    }
  }

  depends_on = [google_project_service.enabled]
}

# ---------------------------------------------------------------- Terraform state bucket for infra/stack

resource "google_storage_bucket" "tf_state" {
  project  = google_project.this.project_id
  name     = "${google_project.this.project_id}-tfstate"
  location = var.region
  labels   = local.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.state_bucket_force_destroy

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.enabled]
}
