-- Sales order headers (VBAK). Cancelled orders are deleted at the source and filtered out here (trap T1).
select
    vbeln                                as order_id,
    kunnr                                as customer_id,
    {{ sap_date('erdat') }}              as order_date,
    auart                                as order_type,
    vkorg                                as sales_org,
    cast(netwr as decimal(18, 2))        as net_value,
    waerk                                as currency,
    {{ sap_date('vdatu') }}              as requested_delivery_date,
    _fivetran_deleted,
    _fivetran_synced
from {{ source('sap_s4', 'vbak') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
