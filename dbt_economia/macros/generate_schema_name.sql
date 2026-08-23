{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- Por padrao o dbt prefixa o schema customizado com o schema do target
        (ex: "public_staging"). Aqui forcamos o nome exato definido no
        dbt_project.yml (ex: apenas "staging"), que fica mais limpo pro
        Power BI se conectar depois. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
