-- Every version of every Salesforce account (history mode). Tier changes keep the old row with its validity period.
select
    id                         as salesforce_account_id,
    name                       as account_name,
    nullif(sap_customer_number_c, '') as sap_customer_number,
    tier_c                     as tier,
    region_c                   as region,
    billing_country,
    owner_id,
    _fivetran_start            as valid_from,
    _fivetran_end              as valid_to,
    _fivetran_active           as is_current
from {{ source('salesforce', 'account') }}
where not _fivetran_deleted and not is_deleted
