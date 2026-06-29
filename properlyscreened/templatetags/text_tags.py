from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()

_THE_SUFFIXES = ('theater', 'theatre', 'cinema', 'archive')


@register.filter(is_safe=True)
@stringfilter
def shy_directors(value):
    """
    Insert a soft hyphen in 'Directors' so it can break as Direct-ors in mobile tables.
    """
    return mark_safe(value.replace('Directors', 'Direc&shy;tors'))


@register.filter(is_safe=True)
@stringfilter
def name_lines(value):
    """
    Put each comma-separated name on its own line.
    """
    return mark_safe(value.replace(', ', ',<br>'))


@register.filter
@stringfilter
def optional_the(value):
    """
    Return 'the' if value (lowercased) ends in theater/theatre/cinema, else ''.
    """
    return 'the' if value.lower().endswith(_THE_SUFFIXES) else ''
