-- Trap T4: which SAP customer each Salesforce account belongs to.
-- An account with an SAP customer number maps directly. An account without one is merged into the customer whose
-- Salesforce account has the same normalised name (legal suffixes such as GmbH removed). Anything else is a prospect.
with current_accounts as (
    select * from {{ ref('stg_salesforce__account_history') }} where is_current
),

mapped as (
    select salesforce_account_id, account_name, sap_customer_number as customer_id,
           {{ normalize_name('account_name') }} as normalized_name
    from current_accounts
    where sap_customer_number is not null
),

unmapped as (
    select salesforce_account_id, account_name, {{ normalize_name('account_name') }} as normalized_name
    from current_accounts
    where sap_customer_number is null
)

select salesforce_account_id, account_name, customer_id, 'sap_customer_number' as match_method
from mapped
union all
select u.salesforce_account_id, u.account_name, m.customer_id, 'normalized_name' as match_method
from unmapped u
join mapped m on m.normalized_name = u.normalized_name
{% if trap_broken('T4') %} where false {% endif %}
