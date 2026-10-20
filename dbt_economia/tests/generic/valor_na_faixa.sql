{% test valor_na_faixa(model, column_name, min_valor, max_valor) %}
{#- Falha para cada linha cujo valor esteja fora de [min_valor, max_valor].
    Detecta erro de escala/unidade, algo que unique e not_null não pegam. -#}
select {{ column_name }} as valor_fora_da_faixa
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < {{ min_valor }} or {{ column_name }} > {{ max_valor }})
{% endtest %}
