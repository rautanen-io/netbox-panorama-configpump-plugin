"""Template code for connection tables."""

# pylint: disable=line-too-long

DEVICES_TEMPLATE = '{% load helpers %}{% for device in record.devices %}{% if not forloop.first %}, {% endif %}<a href="{{ device.get_absolute_url }}">{{ device }}</a>{% empty %}—{% endfor %}'
