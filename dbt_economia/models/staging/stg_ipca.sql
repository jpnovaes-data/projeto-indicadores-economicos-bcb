{#-
    IPCA mensal e acumulado em 12 meses COMPOSTO:

        acumulado = (produto de (1 + variação_mensal/100) nos 12 meses) - 1

    Postgres não tem produto como agregado, então usamos exp(sum(ln(...))).
    O acumulado só existe quando a janela tem exatamente 12 meses CONSECUTIVOS;
    nos primeiros 11 meses (ou após um buraco na série) o valor é nulo.
-#}

with fonte as (
    select * from {{ source('raw', 'ipca') }}
),

base as (
    select data, valor
    from fonte
    where valor is not null
)

select
    data,
    valor as ipca_variacao_mensal,
    case
        when count(*) over janela = 12
         and date_trunc('month', data) - interval '11 months'
             = date_trunc('month', min(data) over janela)
        then round(
            cast((exp(sum(ln(1 + valor / 100.0)) over janela) - 1) * 100 as numeric),
            4
        )
    end as ipca_acumulado_12m
from base
window janela as (order by data rows between 11 preceding and current row)
order by data
