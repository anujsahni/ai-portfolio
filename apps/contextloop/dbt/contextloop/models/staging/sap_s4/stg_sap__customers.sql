-- SAP customer master (KNA1) with plain-English names. Region follows the narrative: US, CA, MX are North America.
select
    kunnr                                               as customer_id,
    name_1                                              as customer_name,
    land_1                                              as country_code,
    ort_01                                              as city,
    case when land_1 in ('US', 'CA', 'MX') then 'North America' else 'EMEA' end as region,
    {{ sap_date('erdat') }}                             as created_on,
    _fivetran_deleted,
    _fivetran_synced
from {{ source('sap_s4', 'kna_1') }}
where {% if trap_broken('T1') %} true {% else %} not _fivetran_deleted {% endif %}
