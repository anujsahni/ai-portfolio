-- Trap T5: the tier of each customer over time, from the history-mode rows of its SAP-mapped Salesforce account.
-- The look-alike duplicate's own tier is ignored (it is not the account of record).
select
    i.customer_id,
    h.tier,
    h.valid_from,
    h.valid_to,
    h.is_current
from {{ ref('stg_salesforce__account_history') }} h
join {{ ref('int_account_identity') }} i
  on i.salesforce_account_id = h.salesforce_account_id and i.match_method = 'sap_customer_number'
