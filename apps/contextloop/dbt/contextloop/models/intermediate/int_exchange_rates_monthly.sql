-- Trap T3: one EUR -> USD monthly average rate (TCURR rate type M) per month; USD converts at 1.
select date_trunc('month', valid_from)::date as rate_month, 'EUR' as currency, rate as usd_rate
from {{ ref('stg_sap__exchange_rates') }}
where rate_type = 'M' and from_currency = 'EUR' and to_currency = 'USD'
