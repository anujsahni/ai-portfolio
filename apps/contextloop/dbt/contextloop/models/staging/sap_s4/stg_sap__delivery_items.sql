-- Delivery items (LIPS). VGBEL is the sales order each delivery item fulfils.
select
    vbeln                                as delivery_id,
    posnr                                as item_number,
    matnr                                as material_id,
    cast(lfimg as integer)               as quantity,
    vgbel                                as order_id,
    vgpos                                as order_item_number,
    _fivetran_deleted
from {{ source('sap_s4', 'lips') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
