-- Zendesk tickets.
select
    id                 as ticket_id,
    organization_id,
    created_at,
    updated_at,
    subject,
    status,
    priority,
    type               as ticket_type
from {{ source('zendesk', 'ticket') }}
where not _fivetran_deleted
