from django import template
from django.template.defaultfilters import filesizeformat

register = template.Library()

@register.filter
def disksizes(value):
    return [filesizeformat(v * 1024**2) for v in value]

@register.filter
def memsize(value):
    return filesizeformat(value * 1024**2)
