# CL-07 completion record: semantic layer with MetricFlow

**Date:** 11 Nov 2026 · **Result:** all acceptance criteria met, with one naming note below.

MetricFlow 0.213 (dbt-metricflow 0.15) runs on DuckDB inside the image, so the fallback (compiling metrics in Python) was not needed.

## Validation

```
✔ 🎉 Successfully validated the semantics of built manifest (ERRORS: 0, FUTURE_ERRORS: 0, WARNINGS: 0)
```
`make build` runs `mf validate-configs` every time.

## Metrics (dbt/contextloop/models/semantic/semantic_models.yml)

`on_time_delivery_rate` (ratio), `late_deliveries`, `deliveries_90d`, `on_time_deliveries_90d`, `net_revenue`,
`open_shipping_tickets`, `renewals_due_120d`, and the derived `account_risk_flag`, over five semantic models (accounts,
deliveries, revenue, tickets, renewals). Every metric has a label and a one-to-three sentence description (tested).

## Saved query next to the hidden truth

`mf query --saved-query at_risk_strategic_accounts` returns the 25 strategic accounts; `account_risk_flag = 1` for exactly:
Galbury Steelworks, Halbrook Fluid Systems, Jormark Paper Mills, Marmark HVAC, Sevland Utilities, Tamford Food Processing,
Tamwick Mining, Vornwick Utilities, Wesmore Energy, which is the hidden truth's list.

## Metric values equal the truth (tests/test_semantic.py)

On-time rate per account (all 120) and overall strategic (86.1%); net revenue per region and quarter and in total; open shipping
tickets per account and for strategic accounts (28); renewals due per account.

## Tier at the time of delivery (trap T5)

```
delivery__tier_at_delivery    on_time_delivery_rate    deliveries_90d
Strategic                                  0.857621               597
Standard                                   0.905575               879
```
Equal to the truth's rate by tier at delivery. Grouping by `account__tier` (today's tier) gives different numbers; the test
asserts they differ.

**Naming note:** the story says "by `account__tier`". In MetricFlow a dimension is named after its semantic model's primary
entity, so the history-correct tier is `delivery__tier_at_delivery`, and `account__tier` is today's tier. Both are exposed; the
metric descriptions and the agent prompt (CL-10) direct tier breakdowns to `delivery__tier_at_delivery`.
