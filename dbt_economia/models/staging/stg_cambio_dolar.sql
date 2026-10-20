with fonte as (
    select * from {{ source('raw', 'cambio_dolar') }}
)

select
    data,
    valor as dolar_venda
from fonte
where valor is not null
order by data
