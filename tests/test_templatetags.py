from properlyscreened.templatetags.text_tags import (
    name_lines,
    optional_the,
    shy_directors,
)
from properlyscreened.templatetags.typefixes import ddyears, typefixes


class TestOptionalThe:
    def test_theater_gets_the(self):
        assert optional_the('The Castro Theatre') == 'the'

    def test_cinema_gets_the(self):
        assert optional_the('Roxie Cinema') == 'the'

    def test_case_insensitive(self):
        assert optional_the('Pacific Film Archive') == 'the'

    def test_other_names_get_nothing(self):
        assert optional_the('Grand Lake') == ''


class TestNameLines:
    def test_commas_become_breaks(self):
        assert name_lines('Keaton, Bruckman') == 'Keaton,<br>Bruckman'

    def test_single_name_unchanged(self):
        assert name_lines('Hitchcock') == 'Hitchcock'


class TestShyDirectors:
    def test_inserts_soft_hyphen(self):
        assert shy_directors('Directors') == 'Direc&shy;tors'

    def test_leaves_other_text_alone(self):
        assert shy_directors('Critics') == 'Critics'


class TestDdyears:
    def test_straight_apostrophe_before_year_becomes_curly(self):
        assert ddyears("class of '99") == 'class of ’99'

    def test_leaves_other_apostrophes_alone(self):
        assert ddyears("it's fine") == "it's fine"


class TestTypefixes:
    def test_possessive_after_link_gets_closing_quote(self):
        result = typefixes('<a href="/x/">Hitchcock</a>\'s film')
        assert '&#8217;s' in result
        assert '&#8216;' not in result
