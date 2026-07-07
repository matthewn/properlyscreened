from types import SimpleNamespace

from properlyscreened.models import (
    BasePage,
    _flow_inline,
    _last_names,
    _parse_sort,
    _sort_headers,
    _sort_key,
)


class TestSortKey:
    def test_accents_fold_to_base_letter(self):
        assert _sort_key('À bout de souffle') == _sort_key('a bout de souffle')

    def test_case_insensitive(self):
        assert _sort_key('ZOO') == _sort_key('zoo')

    def test_orders_accented_with_its_base_letter(self):
        assert _sort_key('Ápple') < _sort_key('banana')


class TestLastNames:
    def test_reduces_to_surnames(self):
        assert _last_names('Buster Keaton, Clyde Bruckman') == 'Keaton, Bruckman'

    def test_single_name(self):
        assert _last_names('Hitchcock') == 'Hitchcock'

    def test_skips_empty_parts(self):
        assert _last_names('Buster Keaton, , Clyde Bruckman') == 'Keaton, Bruckman'

    def test_empty_string(self):
        assert _last_names('') == ''


class TestFlowInline:
    def test_block_boundaries_become_single_space(self):
        assert _flow_inline('<p>one</p><p>two</p>') == 'one two'

    def test_inline_styling_preserved(self):
        assert _flow_inline('<p>a <em>b</em> c</p>') == 'a <em>b</em> c'

    def test_collapses_runs_of_whitespace(self):
        assert _flow_inline('<p>a</p>\n\n  <p>b</p>') == 'a b'


class TestSortHeaders:
    COLUMNS = [('title', 'Title'), ('year', 'Year')]

    def test_active_ascending_shows_up_arrow_and_links_to_desc(self):
        # clicking the active asc column reverses it, so its link is not clean
        title = _sort_headers(self.COLUMNS, 'title', 'asc', 'title')[0]
        assert title['arrow'] == '▲'
        assert 'sort=title' in title['query'] and 'dir=desc' in title['query']

    def test_active_descending_shows_down_arrow(self):
        year = next(
            h for h in _sort_headers(self.COLUMNS, 'year', 'desc', 'title')
            if h['label'] == 'Year'
        )
        assert year['arrow'] == '▼'

    def test_default_column_link_is_clean_when_it_would_produce_default_asc(self):
        # title is the default column and currently inactive, so its link is the
        # bare (query-string-free) default view
        title = _sort_headers(self.COLUMNS, 'year', 'asc', 'title')[0]
        assert title['query'] == ''
        assert title['arrow'] == ''

    def test_inactive_column_links_ascending_and_has_no_arrow(self):
        year = _sort_headers(self.COLUMNS, 'title', 'asc', 'title')[1]
        assert 'dir=asc' in year['query'] and 'sort=year' in year['query']
        assert year['arrow'] == ''


class TestParseSort:
    COLUMNS = [('rank', 'Ranking'), ('title', 'Title')]

    def _request(self, **params):
        return SimpleNamespace(GET=params)

    def test_valid_selection(self):
        assert _parse_sort(self._request(sort='title', dir='desc'), self.COLUMNS, 'rank') == (
            'title', 'desc',
        )

    def test_unknown_sort_falls_back_to_default(self):
        assert _parse_sort(self._request(sort='bogus'), self.COLUMNS, 'rank') == ('rank', 'asc')

    def test_missing_params_fall_back_to_default(self):
        assert _parse_sort(self._request(), self.COLUMNS, 'rank') == ('rank', 'asc')

    def test_invalid_direction_defaults_to_asc(self):
        assert _parse_sort(self._request(sort='title', dir='sideways'), self.COLUMNS, 'rank') == (
            'title', 'asc',
        )


class TestExcerpt:
    """
    BasePage.excerpt only reads self.body, so it can be exercised on a stand-in
    without touching the database.
    """

    def _page(self, prose):
        block = SimpleNamespace(block_type='rich_text', value=prose)
        return SimpleNamespace(body=[block])

    def test_short_prose_is_not_truncated(self):
        html, is_truncated = BasePage.excerpt(self._page('<p>a few short words</p>'))
        assert is_truncated is False
        assert 'a few short words' in html

    def test_long_prose_is_truncated_on_word_boundary(self):
        words = ' '.join(f'word{i}' for i in range(50))
        html, is_truncated = BasePage.excerpt(self._page(f'<p>{words}</p>'), max_words=5)
        assert is_truncated is True
        # only the first 5 words survive
        assert 'word4' in html and 'word5' not in html

    def test_trailing_punctuation_before_cut_is_trimmed(self):
        # cut lands right after a dash run, which should be stripped so it does
        # not collide with an appended ellipsis
        prose = '<p>alpha beta gamma delta-- epsilon zeta eta theta</p>'
        html, is_truncated = BasePage.excerpt(self._page(prose), max_words=4)
        assert is_truncated is True
        assert '--' not in html
        assert 'delta' in html
