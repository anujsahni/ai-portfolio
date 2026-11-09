variable "name_prefix" {
  description = "Unique prefix for resource names, e.g. dealpulse-a1b2 (set by make configure)."
  type        = string

  validation {
    condition     = can(regex("^dealpulse-[a-z0-9]{4}$", var.name_prefix))
    error_message = "name_prefix must look like dealpulse-xxxx (4 lowercase letters or digits). Run make configure."
  }
}

variable "region" {
  description = "AWS region for every DealPulse resource. us-east-1 has the widest Bedrock model availability."
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_force_destroy" {
  description = "Allow deleting the state bucket with objects in it. Only make destroy-all sets this to true."
  type        = bool
  default     = false
}

variable "budget_amount_usd" {
  description = "Monthly cost budget for resources tagged app=dealpulse."
  type        = number
  default     = 60
}

variable "alert_emails" {
  description = "Email addresses that receive budget alerts (kept in the git-ignored terraform.tfvars)."
  type        = list(string)

  validation {
    condition     = length(var.alert_emails) > 0 && alltrue([for e in var.alert_emails : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", e))])
    error_message = "Set at least one valid email in alert_emails."
  }
}
