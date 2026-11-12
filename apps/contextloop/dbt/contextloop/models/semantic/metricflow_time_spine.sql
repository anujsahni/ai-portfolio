-- Daily time spine MetricFlow uses for time-based joins and grains.
{{ config(materialized='table', schema='marts') }}
select cast(range as date) as date_day
from range(date '2024-01-01', date '2028-01-01', interval 1 day)
