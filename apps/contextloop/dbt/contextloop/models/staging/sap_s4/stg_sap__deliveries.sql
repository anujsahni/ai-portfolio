-- Delivery headers (LIKP). WADAT and WADAT_IST are goods-issue (ship) dates, not delivery dates (trap T2).
-- ZZ_CARRIER_ID arrived later at the source (schema change); before that it is null.
select
    vbeln                                as delivery_id,
    kunnr                                as customer_id,
    vstel                                as shipping_point,
    {{ sap_date('erdat') }}              as created_on,
    {{ sap_date('wadat') }}              as planned_goods_issue_date,
    {{ sap_date('wadat_ist') }}          as actual_goods_issue_date,
    {{ sap_date('lfdat') }}              as planned_delivery_date,
    {{ optional_column(source('sap_s4', 'likp'), 'zz_carrier_id') }} as carrier_id,
    _fivetran_deleted,
    _fivetran_synced
from {{ source('sap_s4', 'likp') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
