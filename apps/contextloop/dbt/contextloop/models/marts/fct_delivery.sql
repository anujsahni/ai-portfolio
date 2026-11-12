-- One row per non-cancelled delivery: promised date, actual delivery time, on-time flag, and the customer's tier on the
-- requested delivery date (so metrics by tier use the tier in force at the time, not today's).
select
    d.delivery_id::varchar                      as delivery_id,
    d.customer_id::varchar                      as customer_id,
    d.order_id::varchar                         as order_id,
    d.requested_delivery_date::date             as requested_delivery_date,
    d.planned_goods_issue_date::date            as planned_goods_issue_date,
    d.actual_goods_issue_date::date             as actual_goods_issue_date,
    d.delivered_at::timestamptz                 as delivered_at,
    d.is_delivered::boolean                     as is_delivered,
    d.is_on_time::boolean                       as is_on_time,
    (not d.is_on_time)::boolean                 as is_late,
    d.days_late::integer                        as days_late,
    d.carrier_code::varchar                     as carrier_code,
    coalesce(t.tier, 'Standard')::varchar       as tier_at_delivery,
    (d.requested_delivery_date between {{ as_of() }} - {{ var('window_days') - 1 }} and {{ as_of() }})::boolean as is_in_90d_window
from {{ ref('int_deliveries_enriched') }} d
left join {{ ref('int_account_tier_history') }} t
  on t.customer_id = d.customer_id
 and t.valid_from <= {{ end_of_day('d.requested_delivery_date') }}
 and t.valid_to >= {{ end_of_day('d.requested_delivery_date') }}
