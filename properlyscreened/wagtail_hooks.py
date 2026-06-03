from wagtail import hooks
from wagtail.admin.search import SearchArea
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import IndexView, SnippetViewSet
from django.templatetags.static import static
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html

from .models import Film


@hooks.register('insert_global_admin_css')
def global_admin_css():
    return format_html('<link rel="stylesheet" href="{}">', static('css/wagtail_admin.css'))


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
    list_per_page = 10000
    ordering = ['title']


register_snippet(FilmViewSet)
