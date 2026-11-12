-- Zendesk organizations. external_id holds the Salesforce account ID.
select id as organization_id, name as organization_name, external_id as salesforce_account_id
from {{ source('zendesk', 'organization') }}
where not _fivetran_deleted
