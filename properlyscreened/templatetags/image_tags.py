from django import template

from wagtail.images import get_image_model

register = template.Library()


@register.simple_tag
def image_by_id(pk):
    # returns the Wagtail image with the given id, or None if missing
    return get_image_model().objects.filter(pk=pk).first()
