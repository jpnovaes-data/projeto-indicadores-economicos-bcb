with fonte as (
    select * from {{ source('raw', 'selic') }}
)

select
    data,
    valor as selic_ao_dia
from fonte
where valor is not null
order by data
