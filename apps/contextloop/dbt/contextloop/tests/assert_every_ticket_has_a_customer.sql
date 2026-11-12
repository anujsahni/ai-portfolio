-- Identity resolution (trap T4): every ticket from a customer organization must resolve to an SAP customer.
-- Fails if the look-alike duplicate account is not merged, because its tickets would belong to nobody.
select ticket_id, salesforce_account_id
from {{ ref('fct_ticket') }}
where customer_id is null
