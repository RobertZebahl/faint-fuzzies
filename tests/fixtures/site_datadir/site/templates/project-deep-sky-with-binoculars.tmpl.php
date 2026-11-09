{% for obj in OBJECTS %}<h4>{{ obj.NAME }}</h4> [{{ obj.LIST_FILTER }}]
{% for o in obj.OBSERVATIONS_HEADER %}{% for i in o.IMAGES %}<img src="{{ i }}">
{% endfor %}{% endfor %}{% for o in obj.OBSERVATIONS %}{% for i in o.IMAGES %}<img src="{{ i }}">
{% endfor %}{% endfor %}{% endfor %}
