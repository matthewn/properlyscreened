from wagtail import hooks
from wagtail.admin.rich_text.converters.html_to_contentstate import InlineStyleElementHandler
from wagtail.admin.rich_text.editors.draftail.features import InlineStyleFeature
from wagtail.admin.search import SearchArea
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import IndexView, SnippetViewSet
from taggit.models import Tag
from django.templatetags.static import static
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html

from .models import Film


@hooks.register('register_rich_text_features')
def register_small_feature(features):
    """Add a toolbar button that wraps the selection in <small></small>."""
    feature_name = 'small'
    type_ = 'SMALL'

    features.register_editor_plugin(
        'draftail',
        feature_name,
        InlineStyleFeature({
            'type': type_,
            'icon': 'small',
            'description': 'Small',
            'style': {'fontSize': '0.8em'},
        }),
    )
    features.register_converter_rule('contentstate', feature_name, {
        'from_database_format': {'small': InlineStyleElementHandler(type_)},
        'to_database_format': {'style_map': {type_: 'small'}},
    })


@hooks.register('insert_global_admin_css')
def global_admin_css():
    return format_html('<link rel="stylesheet" href="{}">', static('css/wagtail_admin.css'))


@hooks.register('insert_global_admin_js')
def global_admin_js():
    return format_html(
        '<script src="{}"></script><script src="{}"></script>',
        static('js/review_film_autofill.js'),
        static('js/blog_category_icon.js'),
    )


@hooks.register('register_icons')
def register_icons(icons):
    return icons + [
        'properlyscreened/icons/small.svg',
        'properlyscreened/icons/fleuron.svg',
        'properlyscreened/icons/blog_events.svg',
        'properlyscreened/icons/blog_ss.svg',
        'properlyscreened/icons/blog_celebrations.svg',
        'properlyscreened/icons/blog_formats.svg',
        'properlyscreened/icons/blog_theaters.svg',
        'properlyscreened/icons/blog_photography.svg',
        'properlyscreened/icons/blog_profile.svg',
        'properlyscreened/icons/blog_news.svg',
    ]


@hooks.register('register_admin_search_area')
def register_film_search_area():
    # Surface Films in the global admin search (snippets aren't included by
    # default); links to the Film listing, which supports ?q= search.
    return SearchArea(
        'Films',
        reverse('wagtailsnippets_properlyscreened_film:list'),
        name='films',
        icon_name='doc-full-inverse',
        order=200,
    )


class FilmIndexView(IndexView):
    @cached_property
    def columns(self):
        columns = super().columns
        for column in columns:
            if column.name == 'title':
                column.width = '400'
            if column.name == 'year':
                column.width = '50'
        return columns


class FilmViewSet(SnippetViewSet):
    model = Film
    index_view_class = FilmIndexView
    list_display = ['title', 'year', 'director']
    list_per_page = 1000
    ordering = ['title']


class TagViewSet(SnippetViewSet):
    model = Tag
    icon = 'tag'
    list_display = ['name', 'slug']
    list_per_page = 1000
    ordering = ['name']


register_snippet(FilmViewSet)
register_snippet(TagViewSet)
