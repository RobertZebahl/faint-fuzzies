<h3>{{ OBJECT_TITLE }}</h3>
{% if IMAGE %}<a href="{{ IMAGE_LINK }}"><img src="{{ IMAGE }}"></a>
{% endif %}
{% for descr in DESCRIPTIONS %}{% for IMAGE in descr.IMAGES %}<img src="{{ IMAGE }}">
{% endfor %}{% endfor %}
