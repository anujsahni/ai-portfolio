-- Trap T3: every billing document has a USD rate, so no EUR amount is ever summed as if it were USD.
select billing_id, document_currency
from {{ ref('fct_revenue') }}
where usd_rate is null or amount_usd is null
