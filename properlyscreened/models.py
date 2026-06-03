import unicodedata
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, TitleFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.images import get_image_model_string
from wagtail.images.models import Image, AbstractImage, AbstractRendition
from wagtail.snippets.models import register_snippet

from wagtailautocomplete.edit_handlers import AutocompletePanel

from wagtailmedia.models import Media, AbstractMedia

from .blocks import LoadedStreamBlock


def _sort_key(value):
    """
    Accent- and case-insensitive sort key, so e.g. 'À' sorts with 'A'.
    """
    decomposed = unicodedata.normalize('NFKD', value)
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _sort_headers(columns, active, direction, default_key):
    """
    Build the header link/indicator data for a sortable table. Clicking the
    active column reverses it; any other column sorts ascending. The default
    column+ascending gets a clean (query-string-free) URL.
    """
    headers = []
    for key, label in columns:
        is_active = key == active
        next_dir = ('desc' if direction == 'asc' else 'asc') if is_active else 'asc'
        if key == default_key and next_dir == 'asc':
            query = ''
        else:
            query = '?' + urlencode({'sort': key, 'dir': next_dir})
        headers.append({
            'label': label,
            'query': query,
            'arrow': ('▲' if direction == 'asc' else '▼') if is_active else '',
        })
    return headers


def _review_urls_by_film(film_ids):
    """
    Map film id -> URL of a live Review for that film, where one exists.
    (If a film has several, the first by tree order wins.)
    """
    urls = {}
    for review in Review.objects.live().filter(film_id__in=film_ids):
        urls.setdefault(review.film_id, review.url)
    return urls


# ···························································
# CUSTOM BASE PAGE MODEL AND MISC PAGES/SNIPPETS
# ···························································

class BasePage(Page):
    def get_context(self, request):
        context = super().get_context(request)
        # extras go here
        return context

    class Meta:
        abstract = True


class FlexiblePage(BasePage):
    body = StreamField(
        LoadedStreamBlock(),
    )

    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]


class Review(BasePage):
    use_manual_page_title = models.BooleanField(
        default=False,
    )
    film = models.ForeignKey(
        'Film',
        on_delete=models.PROTECT,
        related_name='reviews',
    )
    theater = models.ForeignKey(
        'Theater',
        on_delete=models.PROTECT,
        related_name='reviews',
    )
    date_screened = models.DateField(
        default=timezone.localdate,
    )
    image = models.ForeignKey(
        get_image_model_string(),
        verbose_name='Image',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    body = StreamField(
        LoadedStreamBlock(),
    )

    content_panels = [
        TitleFieldPanel(
            'title',
            help_text='This value is only shown to site visitors if you check '
                      '“Use manual page title” below.',
        ),
        FieldPanel('use_manual_page_title'),
        AutocompletePanel('film'),
        AutocompletePanel('theater'),
        FieldPanel('date_screened'),
        FieldPanel('image'),
        FieldPanel('body'),
    ]

    @property
    def display_title(self):
        """
        Return a computed title, unless a manual one is set.
        """
        if self.use_manual_page_title:
            return self.title
        critics = self.film.rankings.filter(list_id=settings.BFI_250_LIST_ID).first()
        if critics:
            prefix = f'#{critics.rank}'
        else:
            directors = self.film.rankings.filter(list_id=settings.BFI_DIRECTORS_100_LIST_ID).first()
            prefix = f"#{directors.rank} (Directors' list)" if directors else ''
        title = f'{self.film.title} ({self.film.director}) at {self.theater.name}'
        return f'{prefix} {title}'.strip()


@register_snippet
class Theater(models.Model):
    name = models.CharField(max_length=128)

    panels = [
        FieldPanel('name'),
    ]

    autocomplete_search_field = 'name'

    def autocomplete_label(self):
        return self.name

    @classmethod
    def autocomplete_create(kls, value):
        # allow creating a Theater inline from the text typed into the
        # autocomplete widget; reuse an existing name (case-insensitively) so
        # we never violate the unique_theater_name_ci constraint
        existing = kls.objects.filter(name__iexact=value).first()
        return existing or kls.objects.create(name=value)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='unique_theater_name_ci',
            ),
        ]

    def __str__(self):
        return self.name


class ListPage(BasePage):
    short_name = models.CharField(
        max_length=128,
        help_text='Short name for the list (appears on Lists index and here in the admin).',
    )

    content_panels = Page.content_panels + [
        FieldPanel('short_name'),
    ]

    parent_page_types = ['properlyscreened.ListIndexPage']
    subpage_types = []

    # (query value, column heading) for the sortable rankings table.
    SORT_COLUMNS = [
        ('rank', 'Ranking'),
        ('title', 'Title'),
        ('year', 'Year(s)'),
        ('director', 'Director(s)'),
    ]

    def __str__(self):
        return self.short_name

    def get_context(self, request):
        context = super().get_context(request)

        sort = request.GET.get('sort')
        direction = request.GET.get('dir')
        if sort not in {key for key, _ in self.SORT_COLUMNS}:
            sort, direction = 'rank', 'asc'
        elif direction not in ('asc', 'desc'):
            direction = 'asc'

        # Sort in Python: SQLite orders text by code point and ignores
        # non-ASCII case/accents, which buries titles like "À bout de souffle".
        # The text columns use an accent-/case-folded key (see _sort_key).
        sort_keys = {
            'rank': lambda r: r.rank,
            'title': lambda r: _sort_key(r.film.title),
            'year': lambda r: r.film.year,
            'director': lambda r: _sort_key(r.film.director),
        }
        rankings = list(self.rankings.select_related('film'))
        review_urls = _review_urls_by_film([r.film_id for r in rankings])
        for r in rankings:
            r.review_url = review_urls.get(r.film_id)
        # Ties fall back to rank, except a rank sort falls back to title.
        # A stable two-pass sort keeps the tie-break ascending even when the
        # primary column is reversed.
        tiebreak = (lambda r: _sort_key(r.film.title)) if sort == 'rank' else (lambda r: r.rank)
        rankings.sort(key=tiebreak)
        rankings.sort(key=sort_keys[sort], reverse=(direction == 'desc'))
        context['rankings'] = rankings

        context['sort_headers'] = _sort_headers(self.SORT_COLUMNS, sort, direction, 'rank')
        return context


class ListIndexPage(BasePage):
    """
    Parents the List pages and shows every ranked film in one sortable table,
    with a Ranking column per child List (headed by its short_name).
    """
    body = StreamField(
        LoadedStreamBlock(),
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel('body'),
    ]

    subpage_types = ['properlyscreened.ListPage']

    # The film columns; a Ranking column per child List is prepended at
    # runtime (keyed 'list<id>'), so the rankings sit to the left.
    FILM_COLUMNS = [
        ('title', 'Title'),
        ('year', 'Year(s)'),
        ('director', 'Director(s)'),
    ]

    def get_context(self, request):
        context = super().get_context(request)

        lists = list(ListPage.objects.child_of(self))
        columns = [(f'list{lst.id}', lst.short_name) for lst in lists] + self.FILM_COLUMNS
        context['published_lists'] = [lst for lst in lists if lst.live]

        sort = request.GET.get('sort')
        direction = request.GET.get('dir')
        if sort not in {key for key, _ in columns}:
            sort, direction = 'title', 'asc'
        elif direction not in ('asc', 'desc'):
            direction = 'asc'

        # One row per film, holding its rank on each list (absent if unranked).
        rows_by_film = {}
        for ranking in Ranking.objects.filter(list__in=lists).select_related('film'):
            row = rows_by_film.setdefault(
                ranking.film_id, {'film': ranking.film, 'ranks': {}}
            )
            row['ranks'][ranking.list_id] = ranking.rank
        rows = list(rows_by_film.values())

        # Baseline tie-break: title ascending, preserved by later stable sorts.
        rows.sort(key=lambda row: _sort_key(row['film'].title))
        reverse = direction == 'desc'
        if sort in ('title', 'year', 'director'):
            text_keys = {
                'title': lambda row: _sort_key(row['film'].title),
                'year': lambda row: row['film'].year,
                'director': lambda row: _sort_key(row['film'].director),
            }
            rows.sort(key=text_keys[sort], reverse=reverse)
        else:
            # A Ranking column. Unranked films sort to the bottom either way.
            list_id = int(sort[len('list'):])
            ranked = [row for row in rows if list_id in row['ranks']]
            unranked = [row for row in rows if list_id not in row['ranks']]
            ranked.sort(key=lambda row: row['ranks'][list_id], reverse=reverse)
            rows = ranked + unranked

        # Flatten each row's ranks into the list-column order for the template.
        list_ids = [lst.id for lst in lists]
        review_urls = _review_urls_by_film([row['film'].id for row in rows])
        context['rows'] = [
            {
                'film': row['film'],
                'ranks': [row['ranks'].get(lid) for lid in list_ids],
                'review_url': review_urls.get(row['film'].id),
            }
            for row in rows
        ]
        context['table_headers'] = _sort_headers(columns, sort, direction, 'title')
        return context


class Film(ClusterableModel):
    title = models.CharField(max_length=128)
    year = models.CharField(max_length=16, verbose_name='Year(s)')
    director = models.CharField(max_length=128, verbose_name='Director(s)')

    panels = [
        FieldPanel('title'),
        FieldPanel('year'),
        FieldPanel('director'),
        InlinePanel('rankings', label='Ranking'),
    ]

    def __str__(self):
        return self.title


class Ranking(models.Model):
    """
    A single Film's numeric placement on a single List.
    """
    film = ParentalKey(
        Film,
        on_delete=models.CASCADE,
        related_name='rankings',
    )
    list = models.ForeignKey(
        ListPage,
        on_delete=models.CASCADE,
        related_name='rankings',
    )
    rank = models.PositiveSmallIntegerField()

    panels = [
        FieldRowPanel([
            FieldPanel('list', widget=forms.Select),
            FieldPanel('rank'),
        ]),
    ]

    class Meta:
        # A film appears at most once per list. Ties are allowed
        # (two films may share the same rank on a list), so (list, rank)
        # is deliberately NOT constrained.
        constraints = [
            models.UniqueConstraint(
                fields=['film', 'list'],
                name='unique_film_per_list',
            ),
        ]
        ordering = ['rank']

    def __str__(self):
        return f'{self.film} — #{self.rank} on {self.list}'


# ···························································
# CUSTOM MEDIA CLASSES                       (for future use)
# ···························································

class CustomImage(AbstractImage):
    # Add any extra fields to image here

    # eg. To add a caption field:
    # caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        # 'caption',
    )


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, on_delete=models.CASCADE, related_name='renditions')

    class Meta:
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class CustomMedia(AbstractMedia):
    # Add any extra fields to image here

    # eg. To add a caption field:
    # caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Media.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        # 'caption',
    )
