{#- Fails when any row still carries _fivetran_deleted = true (trap T1 must be handled in staging). -#}
{% test no_deleted_rows(model, column_name) %}
select * from {{ model }} where {{ column_name }}
{% endtest %}
