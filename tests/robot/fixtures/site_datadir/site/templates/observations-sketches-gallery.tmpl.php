{% for group in OBJECT_GROUP_LIST %}<h2>{{ group.GROUP_NAME }} ({{ group.COLUMN_COUNT }})</h2>
{% for card in group.SKETCH_LIST %}{% for object in card.OBJECT_LIST %}<h3>{{ object.OBJECT_LINK_NAME }}</h3>
<a href={{ object.OBJECT_LINK }}>
{% endfor %}<img src="{{ card.SKETCH }}">
{{ card.OBSERVER }}
{% endfor %}{% endfor %}
