from django import template

from wagtail.models import Site

register = template.Library()


@register.simple_tag(takes_context=True)
def get_site_root(context):
    # Returns a core.Page (not the specific model) — the site's root page.
    return Site.find_for_request(context['request']).root_page


def has_menu_children(page):
    return page.get_children().live().in_menu().exists()


@register.inclusion_tag('properlyscreened/tags/top_menu.html', takes_context=True)
def top_menu(context, parent, calling_page=None):
    """Top-level menu items: live children of `parent` with "Show in menus" set."""
    menuitems = parent.get_children().live().in_menu()
    for menuitem in menuitems:
        menuitem.show_dropdown = has_menu_children(menuitem)
        # An item is active if the page being rendered is it or one of its descendants.
        menuitem.active = (
            calling_page.path.startswith(menuitem.path) if calling_page else False
        )
    return {
        'calling_page': calling_page,
        'menuitems': menuitems,
        'request': context['request'],
    }


@register.inclusion_tag('properlyscreened/tags/top_menu_children.html', takes_context=True)
def top_menu_children(context, parent):
    """Second-level items beneath a top-level menu item."""
    return {
        'parent': parent,
        'menuitems_children': parent.get_children().live().in_menu(),
        'request': context['request'],
    }
