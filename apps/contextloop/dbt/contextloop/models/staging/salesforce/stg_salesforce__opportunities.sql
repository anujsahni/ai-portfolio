-- Salesforce opportunities (renewals and expansions).
select
    id                         as opportunity_id,
    account_id                 as salesforce_account_id,
    name                       as opportunity_name,
    type                       as opportunity_type,
    stage_name                 as stage,
    close_date,
    amount,
    is_closed,
    is_won,
    owner_id
from {{ source('salesforce', 'opportunity') }}
where not _fivetran_deleted and not is_deleted
