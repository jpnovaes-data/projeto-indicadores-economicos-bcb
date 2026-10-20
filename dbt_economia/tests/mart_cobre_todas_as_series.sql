{#- O mês mais recente de cada série deve estar presente no mart. Protege
    contra um join que descarte meses silenciosamente. -#}
with esperado as (
    select 'dolar' as serie, date_trunc('month', max(data))::date as mes from {{ ref('stg_cambio_dolar') }}
    union all
    select 'selic', date_trunc('month', max(data))::date from {{ ref('stg_selic') }}
    union all
    select 'ipca', date_trunc('month', max(data))::date from {{ ref('stg_ipca') }}
    union all
    select 'igpm', date_trunc('month', max(data))::date from {{ ref('stg_igpm') }}
)

select e.serie, e.mes
from esperado e
left join {{ ref('fato_indicadores_economicos') }} f on f.mes = e.mes
where f.mes is null
