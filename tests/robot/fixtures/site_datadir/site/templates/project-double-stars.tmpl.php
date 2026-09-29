{% for double_star in DOUBLE_STARS %}<h4>{{ double_star.NAME }}</h4> [{{ double_star.LIST_FILTER }}]
{% for o in double_star.OBSERVATIONS_HEADER %}{% for i in o.IMAGES %}<img src="{{ i }}">
{% endfor %}{% endfor %}{% for o in double_star.OBSERVATIONS_VISUAL %}{% for i in o.IMAGES %}<img src="{{ i }}">
{% endfor %}{% endfor %}{% endfor %}
