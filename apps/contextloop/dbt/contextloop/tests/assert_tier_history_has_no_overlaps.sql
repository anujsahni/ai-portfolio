-- Trap T5: a customer's tier versions never overlap, so "the tier on a date" is always one value.
select a.customer_id, a.valid_from, b.valid_from as overlapping_from
from {{ ref('int_account_tier_history') }} a
join {{ ref('int_account_tier_history') }} b
  on a.customer_id = b.customer_id and a.valid_from < b.valid_from and a.valid_to >= b.valid_from
