| total | {{ STATISTICS.HEADER_CELLS | join(" | ") }}
{% for row in STATISTICS.ROWS %}{{ row.CATEGORY }} | {{ row.CELLS | join(" | ") }}
{% endfor %}
| {{ STATISTICS.FOOTER_CELLS | join(" | ") }}
