{#
    Consolida todos os indicadores na granularidade mensal.
    Dolar e SELIC (diarios) sao agregados por media do mes.
    IPCA e IGP-M ja sao mensais, entram direto.
#}

with dolar_mensal as (
    select
        date_trunc('month', data)::date as mes,
        avg(dolar_venda) as dolar_medio_mes,
        min(dolar_venda) as dolar_minimo_mes,
        max(dolar_venda) as dolar_maximo_mes
    from {{ ref('stg_cambio_dolar') }}
    group by 1
),

selic_mensal as (
    select
        date_trunc('month', data)::date as mes,
        avg(selic_ao_dia) as selic_media_mes
    from {{ ref('stg_selic') }}
    group by 1
),

ipca as (
    select
        date_trunc('month', data)::date as mes,
        ipca_variacao_mensal,
        ipca_acumulado_12m
    from {{ ref('stg_ipca') }}
),

igpm as (
    select
        date_trunc('month', data)::date as mes,
        igpm_variacao_mensal
    from {{ ref('stg_igpm') }}
)

select
    coalesce(d.mes, s.mes, i.mes, g.mes) as mes,
    d.dolar_medio_mes,
    d.dolar_minimo_mes,
    d.dolar_maximo_mes,
    s.selic_media_mes,
    i.ipca_variacao_mensal,
    i.ipca_acumulado_12m,
    g.igpm_variacao_mensal
from dolar_mensal d
full outer join selic_mensal s on d.mes = s.mes
full outer join ipca i on coalesce(d.mes, s.mes) = i.mes
full outer join igpm g on coalesce(d.mes, s.mes, i.mes) = g.mes
order by mes
