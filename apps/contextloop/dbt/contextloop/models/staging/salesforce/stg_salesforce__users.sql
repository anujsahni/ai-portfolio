-- Salesforce users (account owners).
select id as user_id, name as user_name, email, title, is_active
from {{ source('salesforce', 'user') }}
where not _fivetran_deleted
