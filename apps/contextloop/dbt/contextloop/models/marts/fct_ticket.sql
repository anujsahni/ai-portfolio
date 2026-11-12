-- One row per support ticket, attributed to a customer through identity resolution (so the look-alike duplicate's tickets
-- count toward the real customer). Shipping-related: a shipping tag, or a shipping word in the subject.
with tags as (
    select ticket_id, string_agg(tag, ',' order by tag) as tags,
           bool_or(tag in ('shipping', 'delivery', 'late_delivery', 'logistics')) as has_shipping_tag
    from {{ ref('stg_zendesk__ticket_tags') }}
    group by 1
)

select
    t.ticket_id::bigint                                   as ticket_id,
    i.customer_id::varchar                                as customer_id,
    o.salesforce_account_id::varchar                      as salesforce_account_id,
    t.created_at::timestamptz                             as created_at,
    t.updated_at::timestamptz                             as updated_at,
    t.status::varchar                                     as status,
    (t.status in ('new', 'open', 'pending', 'hold'))::boolean as is_open,
    t.priority::varchar                                   as priority,
    t.subject::varchar                                    as subject,
    coalesce(g.tags, '')::varchar                         as tags,
    (coalesce(g.has_shipping_tag, false)
     or regexp_matches(lower(t.subject), 'late|delay|shipment|delivery|tracking'))::boolean as is_shipping_related
from {{ ref('stg_zendesk__tickets') }} t
left join {{ ref('stg_zendesk__organizations') }} o on o.organization_id = t.organization_id
left join {{ ref('int_account_identity') }} i on i.salesforce_account_id = o.salesforce_account_id
left join tags g on g.ticket_id = t.ticket_id
