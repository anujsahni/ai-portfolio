-- The at-risk list in SQL, following the narrative's definition: strategic, 90-day on-time rate below 85%, and either
-- 2+ open shipping-related tickets or an open renewal due in 120 days. Read by the activation sync (Act 5).
with deliveries as (
    select customer_id, count(*) as deliveries_90d, count(*) filter (where is_on_time) as on_time_90d,
           count(*) filter (where not is_on_time) as late_90d
    from {{ ref('fct_delivery') }}
    where is_in_90d_window
    group by 1
),

tickets as (
    select customer_id, count(*) as open_shipping_tickets
    from {{ ref('fct_ticket') }}
    where is_open and is_shipping_related and customer_id is not null
    group by 1
),

renewals as (
    select customer_id, min(close_date) as renewal_close_date
    from {{ ref('fct_renewal') }}
    where is_due_in_120d
    group by 1
),

scored as (
    select
        a.customer_id, a.account_name, a.salesforce_account_id, a.region, a.tier, a.is_strategic, a.account_owner,
        coalesce(d.deliveries_90d, 0)          as deliveries_90d,
        coalesce(d.late_90d, 0)                as late_deliveries_90d,
        d.on_time_90d / nullif(d.deliveries_90d, 0)::double as on_time_rate_90d,
        coalesce(t.open_shipping_tickets, 0)   as open_shipping_tickets,
        r.renewal_close_date
    from {{ ref('dim_account') }} a
    left join deliveries d on d.customer_id = a.customer_id
    left join tickets t on t.customer_id = a.customer_id
    left join renewals r on r.customer_id = a.customer_id
)

select
    customer_id::varchar                       as customer_id,
    account_name::varchar                      as account_name,
    salesforce_account_id::varchar             as salesforce_account_id,
    region::varchar                            as region,
    tier::varchar                              as tier,
    is_strategic::boolean                      as is_strategic,
    account_owner::varchar                     as account_owner,
    deliveries_90d::integer                    as deliveries_90d,
    late_deliveries_90d::integer               as late_deliveries_90d,
    round(on_time_rate_90d, 4)::double         as on_time_rate_90d,
    open_shipping_tickets::integer             as open_shipping_tickets,
    renewal_close_date::date                   as renewal_close_date,
    (is_strategic and on_time_rate_90d < {{ var('risk_threshold') }}
     and (open_shipping_tickets >= {{ var('min_open_shipping_tickets') }} or renewal_close_date is not null))::boolean as is_at_risk,
    (case
        when renewal_close_date is not null then 'Executive call before the renewal, with a delivery recovery plan'
        when open_shipping_tickets >= 3 then 'Escalate the open tickets with logistics and give the customer a named contact'
        else 'Share the late-delivery list with the customer and agree new delivery dates'
     end)::varchar                             as next_step,
    {{ as_of() }}::date                        as as_of_date
from scored
