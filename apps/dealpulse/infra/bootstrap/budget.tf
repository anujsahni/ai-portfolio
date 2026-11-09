# ------------------------------------------------------------ Cost budget (IAC-02)
#
# The account has other workloads, so the budget counts only resources tagged app=dealpulse.
# That needs the "app" tag activated as a cost allocation tag. AWS can take up to 24 hours to
# start applying it, and it only counts spend from activation onward.

resource "aws_ce_cost_allocation_tag" "app" {
  tag_key = "app"
  status  = "Active"
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = format("%.2f", var.budget_amount_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:app$dealpulse"]
  }

  # 50%, 80% and 100% of actual spend, and 100% of forecasted spend.
  dynamic "notification" {
    for_each = [
      { type = "ACTUAL", pct = 50 },
      { type = "ACTUAL", pct = 80 },
      { type = "ACTUAL", pct = 100 },
      { type = "FORECASTED", pct = 100 },
    ]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.pct
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = var.alert_emails
    }
  }

  depends_on = [aws_ce_cost_allocation_tag.app]
}
