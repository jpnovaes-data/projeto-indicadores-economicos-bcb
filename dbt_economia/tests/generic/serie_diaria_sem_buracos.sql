{% test serie_diaria_sem_buracos(model, column_name, max_dias) %}
{#- Falha para cada data que vem depois de um intervalo maior que max_dias.
    O limite é por série, pois o calendário difere: o dólar só tem dias úteis (maior
    intervalo real em 9,5 anos: 5 dias, no Carnaval), e a Meta Selic é publicada todo dia. -#}
with ordenado as (
    select
        {{ column_name }} as data_ref,
        lag({{ column_name }}) over (order by {{ column_name }}) as data_anterior
    from {{ model }}
)

select data_ref, data_anterior, (data_ref::date - data_anterior::date) as dias_de_intervalo
from ordenado
where data_anterior is not null
  and (data_ref::date - data_anterior::date) > {{ max_dias }}
{% endtest %}
