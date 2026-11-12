-- One row per non-cancelled delivery with the order's requested date and the carrier's actual delivery time.
-- On time = delivered on or before the requested delivery date (VBAK.VDATU); not delivered by then = late.
with delivery_orders as (
    select delivery_id, min(order_id) as order_id
    from {{ ref('stg_sap__delivery_items') }}
    group by 1
)

select
    d.delivery_id,
    d.customer_id,
    o.order_id,
    o.requested_delivery_date,
    d.planned_goods_issue_date,
    d.actual_goods_issue_date,
    a.delivered_at,
    a.carrier_code,
    d.carrier_id,
    a.delivered_at is not null                                              as is_delivered,
    coalesce(a.delivered_at::date <= o.requested_delivery_date, false)      as is_on_time,
    greatest(0, coalesce(a.delivered_at::date, {{ as_of() }}) - o.requested_delivery_date) as days_late
from {{ ref('stg_sap__deliveries') }} d
join delivery_orders dor on dor.delivery_id = d.delivery_id
join {{ ref('stg_sap__sales_orders') }} o on o.order_id = dor.order_id
left join {{ ref('int_delivery_actuals') }} a on a.delivery_id = d.delivery_id
