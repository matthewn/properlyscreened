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


class List(BasePage):
    short_name = models.CharField(
        max_length=128,
        help_text='Short name for the list (appears on Lists index and here in the admin).',
    )

    content_panels = Page.content_panels + [
        FieldPanel('short_name'),
    ]

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
        # Ties fall back to rank, except a rank sort falls back to title.
        # A stable two-pass sort keeps the tie-break ascending even when the
        # primary column is reversed.
        tiebreak = (lambda r: _sort_key(r.film.title)) if sort == 'rank' else (lambda r: r.rank)
        rankings.sort(key=tiebreak)
        rankings.sort(key=sort_keys[sort], reverse=(direction == 'desc'))
        context['rankings'] = rankings

        # Header links: clicking the active column reverses it; any other
        # column sorts ascending. The default (rank asc) gets a clean URL.
        headers = []
        for key, label in self.SORT_COLUMNS:
            active = key == sort
            next_dir = ('desc' if direction == 'asc' else 'asc') if active else 'asc'
            if key == 'rank' and next_dir == 'asc':
                query = ''
            else:
                query = '?' + urlencode({'sort': key, 'dir': next_dir})
            headers.append({
                'label': label,
                'query': query,
                'arrow': ('▲' if direction == 'asc' else '▼') if active else '',
            })
        context['sort_headers'] = headers
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
        List,
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
