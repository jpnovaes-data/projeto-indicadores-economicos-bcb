{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- Por padrão o dbt prefixa o schema customizado com o schema do target
        (ex.: "public_staging"). Aqui forçamos o nome exato definido no
        dbt_project.yml (ex.: apenas "staging"), mais limpo para ferramentas
        de BI que se conectem ao banco depois. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
