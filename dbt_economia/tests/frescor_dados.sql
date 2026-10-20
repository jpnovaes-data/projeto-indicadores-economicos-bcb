{#- Falha se o último dado de cada série estiver mais velho que a tolerância.
    Evita publicar um dashboard "verde", porém parado no tempo.
    Tolerâncias em dbt_project.yml (vars). -#}
select 'dolar' as serie, max(data) as ultima_data
from {{ ref('stg_cambio_dolar') }}
having max(data) < current_date - {{ var('max_atraso_diario') }}

union all
select 'selic', max(data)
from {{ ref('stg_selic') }}
having max(data) < current_date - {{ var('max_atraso_diario') }}

union all
select 'ipca', max(data)
from {{ ref('stg_ipca') }}
having max(data) < current_date - {{ var('max_atraso_mensal') }}

union all
select 'igpm', max(data)
from {{ ref('stg_igpm') }}
having max(data) < current_date - {{ var('max_atraso_mensal') }}
