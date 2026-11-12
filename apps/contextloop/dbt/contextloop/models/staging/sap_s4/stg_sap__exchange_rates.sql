-- Exchange rates (TCURR). GDATU is stored inverted: valid_from = 99999999 - GDATU.
select
    kurst                                                      as rate_type,
    fcurr                                                      as from_currency,
    tcurr                                                      as to_currency,
    strptime(cast(99999999 - cast(gdatu as bigint) as varchar), '%Y%m%d')::date as valid_from,
    cast(ukurs as double)                                      as rate,
    _fivetran_deleted
from {{ source('sap_s4', 'tcurr') }}
where not _fivetran_deleted
