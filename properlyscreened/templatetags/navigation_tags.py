from django import template

from wagtail.models import Site

register = template.Library()


@register.filter
def page_type(page):
    # lowercase model name of the page's specific type, e.g. 'listpage'
    # (empty for non-page contexts, e.g. the search results page)
    if not hasattr(page, 'specific_class'):
        return ''
    return page.specific_class._meta.model_name


@register.filter
def uses_block(page, block_type):
    """
    True if the page's StreamField body has a top-level block of block_type.
    """
    body = getattr(page, 'body', None)
    return bool(body) and any(child.block_type == block_type for child in body)


@register.simple_tag(takes_context=True)
def get_site_root(context):
    # returns a core.Page (not the specific model) - the site's root page
    return Site.find_for_request(context['request']).root_page


@register.inclusion_tag('properlyscreened/tags/top_menu.html', takes_context=True)
def top_menu(context, parent, calling_page=None):
    """
    Top-level menu items: live children of 'parent' with 'Show in menus' set.
    """
    menuitems = parent.get_children().live().in_menu().specific()
    for menuitem in menuitems:
        # an item is active if the page being rendered is it or one of its descendants
        menuitem.active = (
            calling_page.path.startswith(menuitem.path) if calling_page else False
        )
    return {
        'calling_page': calling_page,
        'menuitems': menuitems,
        'request': context['request'],
    }
