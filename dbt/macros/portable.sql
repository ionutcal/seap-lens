{# The same models run on DuckDB locally and on Athena in the cloud. These cover where their SQL differs. #}

{% macro pick_any(expression) %}{{ adapter.dispatch('pick_any')(expression) }}{% endmacro %}
{% macro default__pick_any(expression) %}any_value({{ expression }}){% endmacro %}
{% macro athena__pick_any(expression) %}arbitrary({{ expression }}){% endmacro %}

{% macro latest_by(value, ordering) %}{{ adapter.dispatch('latest_by')(value, ordering) }}{% endmacro %}
{% macro default__latest_by(value, ordering) %}arg_max({{ value }}, {{ ordering }}){% endmacro %}
{% macro athena__latest_by(value, ordering) %}max_by({{ value }}, {{ ordering }}){% endmacro %}

{% macro approx_median(expression) %}{{ adapter.dispatch('approx_median')(expression) }}{% endmacro %}
{% macro default__approx_median(expression) %}median({{ expression }}){% endmacro %}
{% macro athena__approx_median(expression) %}approx_percentile({{ expression }}, 0.5){% endmacro %}

{% macro row_key(columns) %}{{ adapter.dispatch('row_key')(columns) }}{% endmacro %}
{% macro default__row_key(columns) %}md5(concat_ws('|', {{ columns | join(', ') }})){% endmacro %}
{% macro athena__row_key(columns) %}to_hex(md5(to_utf8(concat_ws('|', {{ columns | join(', ') }})))){% endmacro %}

{% macro date_spine(first_day, last_day) %}{{ adapter.dispatch('date_spine')(first_day, last_day) }}{% endmacro %}
{% macro default__date_spine(first_day, last_day) %}generate_series(date '{{ first_day }}', date '{{ last_day }}', interval 1 day) as days(day){% endmacro %}
{% macro athena__date_spine(first_day, last_day) %}unnest(sequence(date '{{ first_day }}', date '{{ last_day }}', interval '1' day)) as days(day){% endmacro %}
