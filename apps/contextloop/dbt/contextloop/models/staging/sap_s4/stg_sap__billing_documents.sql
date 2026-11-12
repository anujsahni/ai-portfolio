-- Billing documents (VBRK): F2 invoices and G2 credit memos, both stored as positive amounts.
select
    vbeln                                as billing_id,
    fkart                                as billing_type,
    fkart = 'G2'                         as is_credit_memo,
    {{ sap_date('fkdat') }}              as billing_date,
    kunag                                as customer_id,
    cast(netwr as decimal(18, 2))        as net_value,
    waerk                                as currency,
    _fivetran_deleted
from {{ source('sap_s4', 'vbrk') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
