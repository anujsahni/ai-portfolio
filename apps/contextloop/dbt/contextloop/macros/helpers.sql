{#- SAP stores dates as YYYYMMDD text, with 00000000 for "no date". -#}
{% macro sap_date(column) -%}
    case when {{ column }} is null or {{ column }} = '00000000' then null
         else strptime({{ column }}, '%Y%m%d')::date end
{%- endmacro %}

{#- The as-of date as a DATE literal. -#}
{% macro as_of() -%}
    date '{{ var("as_of_date") }}'
{%- endmacro %}

{#- End of a day, for "the tier in force at the end of that day" (history mode). -#}
{% macro end_of_day(d) -%}
    (cast({{ d }} as timestamp) + interval 86399 second)::timestamptz
{%- endmacro %}

{#- Company-name normalisation for identity resolution (T4): lower case, punctuation and legal suffixes removed. -#}
{% macro normalize_name(column) -%}
    trim(regexp_replace(
        regexp_replace(regexp_replace(lower({{ column }}), '[^a-z0-9 ]', ' ', 'g'),
                       '\b(gmbh|ag|inc|llc|ltd|corp|bv|sa|srl|ab)\b', ' ', 'g'),
        '\s+', ' ', 'g'))
{%- endmacro %}

{#- True when `make break TRAP=<trap>` asked to remove this trap's handling. -#}
{% macro trap_broken(trap) -%}
    {{ return(var("break_trap") == trap) }}
{%- endmacro %}

{#- A column that may not exist yet in a landed table (columns added at the source arrive later). -#}
{% macro optional_column(relation, column, data_type="varchar") -%}
    {%- set cols = adapter.get_columns_in_relation(relation) | map(attribute="name") | map("lower") | list -%}
    {%- if column | lower in cols -%} {{ column }} {%- else -%} cast(null as {{ data_type }}) {%- endif -%}
{%- endmacro %}
