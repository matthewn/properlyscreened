import re

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe

from wagtail.models import Page

# Logging of search queries for use with the "Promoted search results" module
# <https://docs.wagtail.org/en/stable/reference/contrib/searchpromotions.html>
# (wagtail.contrib.search_promotions is in INSTALLED_APPS).
from wagtail.contrib.search_promotions.models import Query

from properlyscreened.models import HomePage, _flow_inline


def _clean(text):
    """
    Strip tags and collapse all whitespace to single spaces.
    """
    return re.sub(r'\s+', ' ', strip_tags(text or '')).strip()


def _search_fields(page):
    """
    The result's short non-body fields as plain-text strings (empty ones
    dropped). The page title is already the film title, so films add only
    director/year.
    """
    page = page.specific
    values = [page.title, page.search_description]
    film = getattr(page, 'film', None)
    if film:
        values += [film.director, str(film.year)]
    theater = getattr(page, 'theater', None)
    if theater:
        values += [theater.name, theater.location]
    return [text for text in map(_clean, values) if text]


def _body_text(page):
    """
    The page's body prose as a single plain-text string, or ''.
    """
    body = getattr(page.specific, 'body', None)
    if body is None:
        return ''
    # _flow_inline collapses block boundaries (e.g. paragraph breaks) to spaces,
    # so adjacent paragraphs don't fuse together
    prose = ' '.join(str(b.value) for b in body if b.block_type == 'rich_text')
    return _clean(_flow_inline(prose))


def _excerpt(page, query, radius=30):
    """
    A field line (short fields joined by middots) above a body snippet centred on
    the first matched body word (or the opening words). Each part is its own
    <div>; query matches are wrapped in <mark> throughout.
    """
    terms = {t for t in (t.strip('.,;:!?"\'’“”()').lower() for t in query.split()) if t}

    def matches(word):
        return any(term in word.lower() for term in terms)

    def highlight(text):
        return ' '.join(
            f'<mark>{escape(w)}</mark>' if matches(w) else escape(w) for w in text.split()
        )

    def block(css_class, html):
        return f'<div class="{css_class}">{html}</div>' if html else ''

    # _search_fields always leads with the page title, which the result link
    # already shows; only render the field line when there's more than that
    field_values = _search_fields(page)
    fields = ''
    if len(field_values) > 1:
        fields = block('search-meta-fields', ' &middot; '.join(map(highlight, field_values)))

    words = _body_text(page).split()
    hit = next((i for i, w in enumerate(words) if matches(w)), None)
    start = max(0, hit - radius) if hit is not None else 0
    end = start + 2 * radius
    snippet = highlight(' '.join(words[start:end]))
    if snippet:
        snippet = ('… ' if start > 0 else '') + snippet + (' …' if end < len(words) else '')

    return mark_safe(fields + block('search-body', snippet))


def search(request):
    search_query = request.GET.get('query', None)
    page = request.GET.get('page', 1)

    if search_query:
        search_results = Page.objects.live().search(search_query)

        # Log this query for use with the "Promoted search results" module.
        query = Query.get(search_query)
        query.add_hit()
    else:
        search_results = Page.objects.none()

    # Pagination
    paginator = Paginator(search_results, 100)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    # build a highlighted excerpt for each result on the current page only
    if search_query:
        for result in search_results:
            result.excerpt = _excerpt(result, search_query)

    return TemplateResponse(
        request,
        'search/search.html',
        {
            'search_query': search_query,
            'search_results': search_results,
            'hero': home.hero if (home := HomePage.objects.live().first()) else None,
        },
    )
