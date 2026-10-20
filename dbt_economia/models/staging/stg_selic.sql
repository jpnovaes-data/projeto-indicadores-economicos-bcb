with fonte as (
    select * from {{ source('raw', 'selic') }}
)

select
    data,
    -- série SGS 432: Meta Selic em % ao ANO (não ao dia)
    valor as meta_selic_aa
from fonte
where valor is not null
order by data
