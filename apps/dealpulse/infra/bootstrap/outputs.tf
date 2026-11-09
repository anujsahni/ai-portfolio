output "name_prefix" {
  value = var.name_prefix
}

output "region" {
  value = var.region
}

output "account_id" {
  value     = data.aws_caller_identity.current.account_id
  sensitive = true
}

output "state_bucket" {
  value = aws_s3_bucket.tf_state.bucket
}

output "budget" {
  value = {
    name        = aws_budgets_budget.monthly.name
    amount_usd  = var.budget_amount_usd
    filter      = "tag app=dealpulse"
    alerts      = ["50% actual", "80% actual", "100% actual", "100% forecasted"]
    alert_count = length(var.alert_emails)
  }
}
