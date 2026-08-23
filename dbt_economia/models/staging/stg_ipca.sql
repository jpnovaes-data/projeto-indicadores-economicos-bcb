with fonte as (
    select * from {{ source('raw', 'ipca') }}
)

select
    data,
    valor as ipca_variacao_mensal,
    sum(valor) over (
        order by data
        rows between 11 preceding and current row
    ) as ipca_acumulado_12m
from fonte
where valor is not null
order by data
