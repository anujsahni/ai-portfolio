output "project_id" {
  value = google_project.this.project_id
}

output "project_number" {
  value = google_project.this.number
}

output "region" {
  value = var.region
}

output "state_bucket" {
  value = google_storage_bucket.tf_state.name
}

output "budget" {
  value = {
    name       = google_billing_budget.monthly.display_name
    amount     = "${var.budget_amount_usd} ${var.budget_currency} per month"
    thresholds = concat([for t in local.budget_thresholds : "${t * 100}% actual"], ["100% forecasted"])
    note       = "Alerts only. A budget does not stop spending."
  }
}

output "enabled_services" {
  value = sort(tolist(local.services))
}
