{#- Coerência interna: mínimo <= média <= máximo (com folga p/ arredondamento). -#}
select mes, dolar_minimo_mes, dolar_medio_mes, dolar_maximo_mes
from {{ ref('fato_indicadores_economicos') }}
where dolar_medio_mes is not null
  and (dolar_minimo_mes > dolar_medio_mes + 1e-9
       or dolar_medio_mes > dolar_maximo_mes + 1e-9)
