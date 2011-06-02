from django import template
from django.template.defaultfilters import filesizeformat

register = template.Library()

@register.filter
# truncate after a certain number of characters
def disksizes(value):
    return [filesizeformat(v * 1024**2) for v in value]
