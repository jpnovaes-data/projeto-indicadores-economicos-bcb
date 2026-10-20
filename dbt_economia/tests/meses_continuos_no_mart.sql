{#- Falha para cada mês que vem depois de um "buraco" na tabela fato.
    Um mês faltando distorce médias, o acumulado de 12 meses e os gráficos. -#}
with ordenado as (
    select mes, lag(mes) over (order by mes) as mes_anterior
    from {{ ref('fato_indicadores_economicos') }}
)

select mes, mes_anterior
from ordenado
where mes_anterior is not null
  and mes <> (mes_anterior + interval '1 month')::date
