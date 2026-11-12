-- Renewal opportunities per customer, with whether each is open and due within 120 days of the as-of date.
select
    o.opportunity_id::varchar                     as opportunity_id,
    i.customer_id::varchar                        as customer_id,
    o.close_date::date                            as close_date,
    o.amount::double                              as amount_usd,
    o.stage::varchar                              as stage,
    (not o.is_closed)::boolean                    as is_open,
    o.is_won::boolean                             as is_won,
    (o.close_date - {{ as_of() }})::integer       as days_to_close,
    (not o.is_closed and o.close_date between {{ as_of() }} and {{ as_of() }} + {{ var('renewal_days') }})::boolean as is_due_in_120d
from {{ ref('stg_salesforce__opportunities') }} o
join {{ ref('int_account_identity') }} i on i.salesforce_account_id = o.salesforce_account_id
where o.opportunity_type = 'Renewal'
