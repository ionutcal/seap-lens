select
    cast(day as date) as date_day,
    year(day) as year,
    quarter(day) as quarter,
    month(day) as month
from {{ date_spine('2014-01-01', '2030-12-31') }}
