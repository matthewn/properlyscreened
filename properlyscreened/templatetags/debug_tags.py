from pprint import pformat

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def print(obj):
    """Pretty-print an object's __dict__ (or the value itself) in a <pre> block."""
    text = pformat(vars(obj) if hasattr(obj, '__dict__') else obj)
    return format_html('<pre>{}</pre>', text)
