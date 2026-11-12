-- One row per real customer (SAP customer), with its Salesforce account of record and its tier as of the as-of date.
with tier_now as (
    select customer_id, tier
    from {{ ref('int_account_tier_history') }}
    where valid_from <= {{ end_of_day(as_of()) }} and valid_to >= {{ end_of_day(as_of()) }}
),

sf as (
    select i.customer_id, i.salesforce_account_id, h.account_name, h.owner_id
    from {{ ref('int_account_identity') }} i
    join {{ ref('stg_salesforce__account_history') }} h
      on h.salesforce_account_id = i.salesforce_account_id and h.is_current
    where i.match_method = 'sap_customer_number'
)

select
    c.customer_id::varchar                              as customer_id,
    coalesce(sf.account_name, c.customer_name)::varchar as account_name,
    c.customer_name::varchar                            as sap_customer_name,
    sf.salesforce_account_id::varchar                   as salesforce_account_id,
    c.country_code::varchar                             as country_code,
    c.region::varchar                                   as region,
    coalesce(t.tier, 'Standard')::varchar               as tier,
    (t.tier = 'Strategic')::boolean                     as is_strategic,
    u.user_name::varchar                                as account_owner,
    c.created_on::date                                  as customer_since
from {{ ref('stg_sap__customers') }} c
left join sf on sf.customer_id = c.customer_id
left join tier_now t on t.customer_id = c.customer_id
left join {{ ref('stg_salesforce__users') }} u on u.user_id = sf.owner_id
