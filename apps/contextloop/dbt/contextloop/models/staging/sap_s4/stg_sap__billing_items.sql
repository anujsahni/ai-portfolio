-- Billing items (VBRP). VGBEL is the delivery (invoices) or the invoice (credit memos).
select
    vbeln                                as billing_id,
    posnr                                as item_number,
    matnr                                as material_id,
    cast(netwr as decimal(18, 2))        as net_value,
    vgbel                                as reference_document_id,
    aubel                                as order_id,
    _fivetran_deleted
from {{ source('sap_s4', 'vbrp') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
