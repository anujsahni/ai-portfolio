-- Carrier shipments: one per SAP delivery.
select
    shipment_id,
    delivery_number as delivery_id,
    carrier_code,
    tracking_number,
    status,
    created_at,
    updated_at,
    _fivetran_synced
from {{ source('carrier_pg', 'shipment') }}
where not _fivetran_deleted
