variable "project_id" {
  description = "Globally unique project ID. `make configure` adds a random suffix because deleted IDs are held for about 30 days."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be 6-30 characters: lowercase letters, digits, hyphens; start with a letter; not end with a hyphen."
  }
}

variable "project_name" {
  description = "Display name shown in the console."
  type        = string
  default     = "WeekendWise Demo"
}

variable "region" {
  description = "Region for all resources. Must support the chosen Gemini/embedding models, Cloud Run, and Firestore."
  type        = string
  default     = "us-central1"
}

variable "billing_account_id" {
  description = "Billing account to link. Pass with TF_VAR_billing_account_id; never put it in a file."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}$", var.billing_account_id))
    error_message = "billing_account_id must look like XXXXXX-XXXXXX-XXXXXX (see `gcloud billing accounts list`)."
  }
}

variable "org_id" {
  description = "Optional organization ID to create the project under. Leave null for a personal account."
  type        = string
  default     = null
}

variable "folder_id" {
  description = "Optional folder ID to create the project under. Don't set together with org_id."
  type        = string
  default     = null
}

variable "budget_amount_usd" {
  description = "Monthly budget in USD. Capped at $20 for this demo."
  type        = number
  default     = 20

  validation {
    condition     = var.budget_amount_usd > 0 && var.budget_amount_usd <= 20
    error_message = "budget_amount_usd must be between 1 and 20. The demo budget is capped at $20/month."
  }
}

variable "budget_currency" {
  description = "Currency of the billing account. The budget must use the billing account's currency."
  type        = string
  default     = "USD"
}

variable "alert_emails" {
  description = "Optional extra email recipients for budget alerts. Billing admins are always notified."
  type        = list(string)
  default     = []
}

variable "project_deletion_policy" {
  description = "PREVENT blocks deletion. `make destroy-all` switches it to DELETE just before destroying."
  type        = string
  default     = "PREVENT"

  validation {
    condition     = contains(["PREVENT", "DELETE", "ABANDON"], var.project_deletion_policy)
    error_message = "project_deletion_policy must be PREVENT, DELETE, or ABANDON."
  }
}

variable "state_bucket_force_destroy" {
  description = "Allow deleting the state bucket while it still has objects. Only `make destroy-all` sets this."
  type        = bool
  default     = false
}
