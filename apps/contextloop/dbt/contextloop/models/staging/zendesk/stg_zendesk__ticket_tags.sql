-- Zendesk ticket tags, one row per ticket and tag.
select ticket_id, tag
from {{ source('zendesk', 'ticket_tag') }}
where not _fivetran_deleted
