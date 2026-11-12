-- History mode: every Salesforce account has exactly one current (active) version.
select salesforce_account_id, count(*) filter (where is_current) as active_rows
from {{ ref('stg_salesforce__account_history') }}
group by 1
having count(*) filter (where is_current) <> 1
