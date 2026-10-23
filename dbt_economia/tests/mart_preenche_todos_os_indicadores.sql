{#- Todo mês que TEM dado de um indicador no staging precisa estar PREENCHIDO no mart.

    Este teste substitui o antigo "mart_cobre_todas_as_series", que só conferia se o mês
    existia no mart. O mart monta os meses pela UNIÃO das quatro séries, então aquele
    teste era verdadeiro por construção: um indicador podia ficar 100% nulo e nada falhava.

    Falha para cada par (indicador, mês) com dado no staging e valor nulo (ou mês ausente)
    no mart. Para o IPCA acumulado só se exige o mês em que o staging já o calculou
    (os 11 primeiros meses são nulos por desenho). -#}
with meses_dolar as (
    select distinct date_trunc('month', data)::date as mes from {{ ref('stg_cambio_dolar') }}
),

meses_selic as (
    select distinct date_trunc('month', data)::date as mes from {{ ref('stg_selic') }}
),

meses_ipca as (
    select distinct date_trunc('month', data)::date as mes from {{ ref('stg_ipca') }}
),

meses_ipca_acumulado as (
    select distinct date_trunc('month', data)::date as mes
    from {{ ref('stg_ipca') }}
    where ipca_acumulado_12m is not null
),

meses_igpm as (
    select distinct date_trunc('month', data)::date as mes from {{ ref('stg_igpm') }}
),

esperado as (
    select 'dolar_medio_mes' as indicador, mes from meses_dolar
    union all select 'dolar_minimo_mes', mes from meses_dolar
    union all select 'dolar_maximo_mes', mes from meses_dolar
    union all select 'meta_selic_media_mes', mes from meses_selic
    union all select 'ipca_variacao_mensal', mes from meses_ipca
    union all select 'ipca_acumulado_12m', mes from meses_ipca_acumulado
    union all select 'igpm_variacao_mensal', mes from meses_igpm
)

select e.indicador, e.mes
from esperado e
left join {{ ref('fato_indicadores_economicos') }} f on f.mes = e.mes
where (to_jsonb(f) ->> e.indicador) is null
