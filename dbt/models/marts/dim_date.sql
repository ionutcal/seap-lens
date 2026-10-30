select
    cast(day as date) as date_day,
    year(day) as year,
    quarter(day) as quarter,
    month(day) as month
from generate_series(date '2014-01-01', date '2030-12-31', interval 1 day) as days(day)
