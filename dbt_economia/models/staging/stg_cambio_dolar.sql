with fonte as (
    select * from {{ source('raw', 'cambio_dolar') }}
)

select
    data,
    valor as dolar_venda,
    lag(valor) over (order by data) as dolar_venda_anterior
from fonte
where valor is not null
order by data
