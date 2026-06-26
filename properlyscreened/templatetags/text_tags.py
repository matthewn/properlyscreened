from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

_THE_SUFFIXES = ('theater', 'theatre', 'cinema', 'archive')


@register.filter
@stringfilter
def optional_the(value):
    """Return 'the' if value (lowercased) ends in theater/theatre/cinema, else ''."""
    return 'the' if value.lower().endswith(_THE_SUFFIXES) else ''
