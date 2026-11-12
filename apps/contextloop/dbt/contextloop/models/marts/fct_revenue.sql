-- Billing net of credit memos, in USD (trap T3): each document converts at the monthly average rate of its billing month.
select
    b.billing_id::varchar                                            as billing_id,
    b.customer_id::varchar                                           as customer_id,
    b.billing_date::date                                             as billing_date,
    b.billing_type::varchar                                          as billing_type,
    b.is_credit_memo::boolean                                        as is_credit_memo,
    b.currency::varchar                                              as document_currency,
    (case when b.is_credit_memo then -1 else 1 end * b.net_value)::decimal(18, 2)       as amount_document_currency,
    (case when b.currency = 'USD' then 1 else r.usd_rate end)::double                   as usd_rate,
    round(case when b.is_credit_memo then -1 else 1 end * b.net_value
          * case when b.currency = 'USD' then 1 else r.usd_rate end, 2)::decimal(18, 2)  as amount_usd,
    'USD'::varchar                                                   as reporting_currency,
    c.region::varchar                                                as region,
    (year(b.billing_date) || '-Q' || quarter(b.billing_date))::varchar as billing_quarter
from {{ ref('stg_sap__billing_documents') }} b
join {{ ref('stg_sap__customers') }} c on c.customer_id = b.customer_id
left join {{ ref('int_exchange_rates_monthly') }} r
  on r.currency = b.currency and r.rate_month = date_trunc('month', b.billing_date)
