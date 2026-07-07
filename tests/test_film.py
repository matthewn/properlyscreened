from properlyscreened.models import Film


class TestDirectorShort:
    def test_derives_surnames_when_no_override(self):
        film = Film(director='Buster Keaton, Clyde Bruckman')
        assert film.director_short == 'Keaton, Bruckman'

    def test_override_wins_when_set(self):
        film = Film(
            director='Joel Coen, Ethan Coen',
            director_short_override='The Coens',
        )
        assert film.director_short == 'The Coens'
