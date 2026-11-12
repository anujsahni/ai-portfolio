-- Carrier tracking events. The `delivered` event is the actual delivery time.
select
    event_id,
    shipment_id,
    event_type,
    event_at,
    location
from {{ source('carrier_pg', 'shipment_event') }}
where not _fivetran_deleted
