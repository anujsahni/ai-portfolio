-- Trap T2: when each delivery actually arrived, from the carrier's `delivered` event (not SAP's goods-issue dates).
select
    s.delivery_id,
    s.carrier_code,
    s.tracking_number,
    s.status            as shipment_status,
    min(e.event_at) filter (where e.event_type = 'delivered')  as delivered_at,
    min(e.event_at) filter (where e.event_type = 'picked_up')  as picked_up_at
from {{ ref('stg_carrier__shipments') }} s
left join {{ ref('stg_carrier__shipment_events') }} e on e.shipment_id = s.shipment_id
group by all
