{#
    Consolida os indicadores na granularidade MENSAL (1 linha por mês).
    Dólar e Meta Selic (diários) entram como estatísticas do mês;
    IPCA e IGP-M (mensais) entram direto.
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
        avg(meta_selic_aa) as meta_selic_media_mes
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
),

meses as (
    select mes from dolar_mensal
    union
    select mes from selic_mensal
    union
    select mes from ipca
    union
    select mes from igpm
)

select
    m.mes,
    d.dolar_medio_mes,
    d.dolar_minimo_mes,
    d.dolar_maximo_mes,
    s.meta_selic_media_mes,
    i.ipca_variacao_mensal,
    i.ipca_acumulado_12m,
    g.igpm_variacao_mensal
from meses m
left join dolar_mensal d on d.mes = m.mes
left join selic_mensal s on s.mes = m.mes
left join ipca i on i.mes = m.mes
left join igpm g on g.mes = m.mes
order by m.mes
