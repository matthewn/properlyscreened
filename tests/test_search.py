from types import SimpleNamespace

from django.utils.safestring import SafeString

from search.views import _clean, _excerpt


class TestClean:
    def test_strips_tags_and_collapses_whitespace(self):
        assert _clean('<p>hello   <em>there</em></p>\n world') == 'hello there world'

    def test_handles_none(self):
        assert _clean(None) == ''


def _page(title='', description='', film=None, theater=None, body_prose=''):
    block = SimpleNamespace(block_type='rich_text', value=body_prose)
    page = SimpleNamespace(
        title=title,
        search_description=description,
        film=film,
        theater=theater,
        body=[block],
    )
    # .specific returns the page itself in these unit tests
    page.specific = page
    return page


class TestExcerpt:
    def test_matched_body_word_is_highlighted(self):
        page = _page(title='A Film', body_prose='<p>the quick brown fox jumps</p>')
        html = _excerpt(page, 'brown')
        assert isinstance(html, SafeString)
        assert '<mark>brown</mark>' in html

    def test_field_line_rendered_only_with_extra_fields(self):
        # title alone -> no field line (title is already shown by the result link)
        assert 'search-meta-fields' not in _excerpt(_page(title='Solo'), 'x')
        film = SimpleNamespace(director='Buster Keaton', year=1926)
        with_fields = _excerpt(_page(title='The General', film=film), 'keaton')
        assert 'search-meta-fields' in with_fields
        assert '<mark>Keaton</mark>' in with_fields

    def test_snippet_centres_on_first_match_with_ellipses(self):
        words = ' '.join(f'w{i}' for i in range(100))
        page = _page(title='T', body_prose=f'<p>{words} needle tail</p>')
        html = _excerpt(page, 'needle', radius=3)
        assert '<mark>needle</mark>' in html
        # match is deep in the body, so a leading ellipsis is added
        assert html.startswith('<div class="search-body">…') or '…' in html

    def test_no_body_match_starts_from_opening_words(self):
        page = _page(title='T', body_prose='<p>alpha beta gamma delta</p>')
        html = _excerpt(page, 'zzz', radius=2)
        assert 'alpha' in html
