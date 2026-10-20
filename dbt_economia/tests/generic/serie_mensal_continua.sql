{% test serie_mensal_continua(model, column_name) %}
{#- Falha para cada data que vem depois de um "buraco" numa série MENSAL
    (IPCA, IGP-M). Mês faltando = acumulado de 12 meses nulo/incorreto. -#}
with ordenado as (
    select
        {{ column_name }} as data_ref,
        lag({{ column_name }}) over (order by {{ column_name }}) as data_anterior
    from {{ model }}
)

select data_ref, data_anterior
from ordenado
where data_anterior is not null
  and date_trunc('month', data_ref)
      <> date_trunc('month', data_anterior) + interval '1 month'
{% endtest %}
