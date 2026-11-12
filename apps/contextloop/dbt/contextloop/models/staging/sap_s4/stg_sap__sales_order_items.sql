-- Sales order items (VBAP).
select
    vbeln                                as order_id,
    posnr                                as item_number,
    matnr                                as material_id,
    arktx                                as item_description,
    cast(kwmeng as integer)              as quantity,
    cast(netwr as decimal(18, 2))        as net_value,
    waerk                                as currency,
    _fivetran_deleted
from {{ source('sap_s4', 'vbap') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
