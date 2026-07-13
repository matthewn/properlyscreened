from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from typogrify.templatetags.typogrify_tags import smartypants, typogrify

import re

register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def ddyears(value):
    """ Fix apostrophes before alumni year. """
    regex = re.compile(" ('|‘|&#8216;)(\\d\\d)")
    value = regex.sub(' ’\\g<2>', value)
    return value


@register.filter(is_safe=True)
@stringfilter
def typefixes(text):
    # unescape characters from wagtail richtext filter
    text = text.replace('&quot;', '"')
    text = text.replace('&#x27;', "'")

    text = typogrify(text)
    # smartypants wrongly opens a quote when a possessive/contraction follows a
    # closing tag (e.g. </a>'s); flip it back to a closing quote
    text = re.sub(r'(</[a-z]+>)&#8216;', r'\g<1>&#8217;', text)
    text = ddyears(text)
    return mark_safe(text)


@register.filter(is_safe=True)
@stringfilter
def typefixes_minimal(text):
    """
    A version of the typefixes filter that only applies smartypants instead of
    the whole typogrify suite of fixes.
    """
    # unescape characters from wagtail richtext filter
    text = text.replace('&quot;', '"')
    text = text.replace('&#x27;', "'")

    text = smartypants(text)

    text = ddyears(text)
    return mark_safe(text)
