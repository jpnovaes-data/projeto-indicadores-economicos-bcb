with fonte as (
    select * from {{ source('raw', 'igpm') }}
)

select
    data,
    valor as igpm_variacao_mensal
from fonte
where valor is not null
order by data
