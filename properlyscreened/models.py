import copy
import re
import unicodedata
from collections import Counter
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.functions import Lower
from django.http import Http404
from django.utils import timezone
from django.utils.html import mark_safe, strip_tags
from django.utils.text import Truncator, slugify

from bs4 import BeautifulSoup

from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from taggit.models import Tag, TaggedItemBase

from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, TitleFieldPanel
from wagtail.contrib.routable_page.models import RoutablePageMixin, path
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page, RevisionMixin
from wagtail.search import index
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


def _last_names(names):
    """
    Reduce a comma-separated list of full names to surnames only, e.g.
    'Buster Keaton, Clyde Bruckman' -> 'Keaton, Bruckman'.
    """
    return ', '.join(part.split()[-1] for part in names.split(',') if part.split())


# Block-level tags whose boundaries collapse to spaces in teasers; inline tags
# (em, strong, a, ...) are left in place so styling flows through.
_TEASER_BLOCK_TAGS = ['p', 'blockquote', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'h5', 'br']


def _flow_inline(markup):
    """
    Flatten block structure to single spaces, keeping inline styling.
    """
    soup = BeautifulSoup(markup, 'html.parser')
    for tag in soup.find_all(_TEASER_BLOCK_TAGS):
        tag.insert_after(' ')
        tag.unwrap()
    return re.sub(r'\s+', ' ', str(soup)).strip()


def _review_urls_by_film(film_ids):
    """
    Map film id -> URL of a live ReviewPage for that film, where one exists.
    (If a film has several, the first by tree order wins.)
    """
    urls = {}
    for review in ReviewPage.objects.live().filter(film_id__in=film_ids):
        urls.setdefault(review.film_id, review.url)
    return urls


def _director_review_urls(films):
    """
    Map film id -> filtered ReviewsIndexPage URL for the film's director, for
    directors with two or more live reviews (else absent).
    """
    index = ReviewsIndexPage.objects.live().first()
    if index is None:
        return {}
    counts = Counter(
        ReviewPage.objects.live().values_list('film__director', flat=True)
    )
    return {
        film.id: index.url + index.reverse_subpage(
            'reviews_by_director', args=[slugify(film.director)]
        )
        for film in films
        if counts[film.director] >= 2
    }


# ···························································
# CUSTOM BASE PAGE MODEL AND MISC PAGES/SNIPPETS
# ···························································

class BasePage(Page):
    hero_image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    menu_title = models.CharField(
        max_length=24,
        blank=True,
        help_text='Overrides the page title in site menus.',
    )

    content_panels = Page.content_panels + [
        FieldPanel('hero_image'),
    ]

    # Add menu_title to Wagtail's existing "For site menus" group on the
    # "Promote" pane. deepcopy so we mutate our copy, not the shared
    # Page.promote_panels; next() over a genexpr (vs. a for loop) so the loop
    # var doesn't leak as a class attr.
    promote_panels = copy.deepcopy(Page.promote_panels)
    next(
        group for group in promote_panels
        if group.args and 'show_in_menus' in group.args[0]
    ).args[0].append('menu_title')

    @property
    def hero(self):
        """
        This page's hero_image, or the nearest ancestor's that has one set.
        """
        for page in [self, *reversed(list(self.get_ancestors().specific()))]:
            if getattr(page, 'hero_image', None):
                return page.hero_image
        return None

    class Meta:
        abstract = True


def _review_teasers(reviews):
    """
    Annotate a ReviewPage queryset with teaser/is_truncated, newest first.
    """
    reviews = list(
        reviews
        .select_related('film__image', 'film', 'theater')
        .prefetch_related('film__rankings')
        .order_by('-date_screened', '-id')
    )
    for review in reviews:
        review.teaser, review.is_truncated = review.excerpt()
    return reviews


class ReviewTeasersMixin:
    def get_context(self, request):
        context = super().get_context(request)
        context['review_teasers'] = _review_teasers(ReviewPage.objects.live())
        return context


class HomePage(ReviewTeasersMixin, BasePage):
    blurb = RichTextField(blank=True)
    link_text = models.CharField(max_length=64, blank=True)
    link_page = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    body = StreamField(
        LoadedStreamBlock(),
        blank=True,
    )

    content_panels = BasePage.content_panels + [
        FieldPanel('blurb'),
        FieldRowPanel([
            FieldPanel('link_text'),
            FieldPanel('link_page'),
        ]),
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('body'),
    ]

    max_count = 1

    def get_context(self, request):
        context = super().get_context(request)
        context['reviews_index_page'] = ReviewsIndexPage.objects.live().first()
        return context

    def quotation(self):
        """
        A randomly chosen Quotation, or None if there are none.
        """
        return Quotation.objects.order_by('?').first()


class ScreeningsPage(BasePage):
    parent_page_types = ['properlyscreened.HomePage']
    subpage_types = []
    max_count = 1

    def get_context(self, request):
        context = super().get_context(request)
        screenings = Screening.objects.forthcoming()
        context['hosted_screenings'] = screenings.filter(is_hosted=True)
        context['other_screenings'] = screenings.filter(is_hosted=False)
        context['lists_index_page'] = ListsIndexPage.objects.live().first()
        return context


class ReviewsIndexPage(ReviewTeasersMixin, RoutablePageMixin, BasePage):
    parent_page_types = ['properlyscreened.HomePage']
    subpage_types = ['properlyscreened.ReviewPage']
    max_count = 1

    def _render_filtered(self, request, reviews, kind, label):
        return self.render(request, context_overrides={
            'review_teasers': _review_teasers(reviews),
            'filter_kind': kind,
            'filter_label': label,
        })

    @path('tags/<slug:tag>/')
    def reviews_by_tag(self, request, tag):
        tag_obj = Tag.objects.filter(slug=tag).first()
        if tag_obj is None:
            raise Http404
        reviews = ReviewPage.objects.live().filter(tags__slug=tag)
        return self._render_filtered(request, reviews, 'tag', tag_obj.name)

    @path('theater/<slug:theater_slug>/')
    def reviews_by_theater(self, request, theater_slug):
        theater = next(
            (t for t in Theater.objects.all() if slugify(t.name) == theater_slug),
            None,
        )
        if theater is None:
            raise Http404
        reviews = ReviewPage.objects.live().filter(theater=theater)
        return self._render_filtered(request, reviews, 'theater', theater.name)

    @path('director/<slug:director_slug>/')
    def reviews_by_director(self, request, director_slug):
        director = next(
            (d for d in Film.objects.values_list('director', flat=True).distinct()
             if slugify(d) == director_slug),
            None,
        )
        if director is None:
            raise Http404
        reviews = ReviewPage.objects.live().filter(film__director=director)
        return self._render_filtered(request, reviews, 'director', director)


class ReviewPageTag(TaggedItemBase):
    content_object = ParentalKey(
        'ReviewPage',
        on_delete=models.CASCADE,
        related_name='tagged_items',
    )


class ReviewPage(BasePage):
    parent_page_types = ['properlyscreened.ReviewsIndexPage']
    subpage_types = []

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
    letterboxd_url = models.URLField(
        'Letterboxd URL',
        blank=True,
    )
    has_spoilers = models.BooleanField(
        default=False,
        help_text='Check the box if the review contains spoilers.',
    )
    tags = ClusterTaggableManager(through=ReviewPageTag, blank=True)
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
        FieldPanel('body'),
        FieldPanel('tags'),
        FieldPanel('letterboxd_url'),
        FieldPanel('has_spoilers'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('body'),
        index.RelatedFields('film', [
            index.SearchField('title'),
            index.SearchField('director'),
            index.SearchField('year'),
        ]),
        index.RelatedFields('theater', [
            index.SearchField('name'),
            index.SearchField('location'),
        ]),
    ]

    def get_context(self, request):
        context = super().get_context(request)
        context['reviews_index'] = self.get_parent().specific
        live = ReviewPage.objects.live()
        context['theater_has_others'] = live.filter(theater=self.theater).count() > 1
        context['director_has_others'] = live.filter(film__director=self.film.director).count() > 1
        return context

    def excerpt(self, max_words=80):
        """
        Return (html, is_truncated): the body's prose cut to `max_words` on a word
        boundary, with paragraph breaks flattened to spaces but inline styling
        (italics, links, ...) preserved.
        """
        prose = ' '.join(
            str(block.value) for block in self.body if block.block_type == 'rich_text'
        )
        flowed = _flow_inline(prose)
        is_truncated = len(strip_tags(flowed).split()) > max_words
        truncated = Truncator(flowed).words(max_words, truncate='', html=True)
        if is_truncated:
            # Drop trailing punctuation so it doesn't collide with the appended
            # ellipsis. Dashes are still raw here (pre-typefixes), so em/en dashes
            # may appear as hyphen runs (-- / ---), not unicode dashes. Regex (not
            # endswith) because the punctuation may sit before closing tags, e.g.
            # "aside--</em>", when the cut lands inside italics.
            truncated = re.sub(r'(?:[,;:]|-{2,}|[—–])(\s*(?:</[^>]+>)*\s*)$', r'\1', truncated)
        return mark_safe(truncated), is_truncated

    @property
    def display_title(self):
        if self.use_manual_page_title:
            return self.title
        else:
            return self.film.title


class ListsIndexPage(BasePage):
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

    search_fields = Page.search_fields + [
        index.SearchField('body'),
    ]

    subpage_types = ['properlyscreened.ListPage']
    max_count = 1

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

        default_sort = columns[0][0]
        sort = request.GET.get('sort')
        direction = request.GET.get('dir')
        if sort not in {key for key, _ in columns}:
            sort, direction = default_sort, 'asc'
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
        director_urls = _director_review_urls([row['film'] for row in rows])
        context['rows'] = [
            {
                'film': row['film'],
                'ranks': [row['ranks'].get(lid) for lid in list_ids],
                'review_url': review_urls.get(row['film'].id),
                'director_url': director_urls.get(row['film'].id),
            }
            for row in rows
        ]
        context['table_headers'] = _sort_headers(columns, sort, direction, default_sort)
        return context


class ListPage(BasePage):
    short_name = models.CharField(
        max_length=128,
        help_text='Short name for the list (appears on Lists index and here in the admin).',
    )

    body = StreamField(
        LoadedStreamBlock(),
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel('short_name'),
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('body'),
    ]

    parent_page_types = ['properlyscreened.ListsIndexPage']
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
        director_urls = _director_review_urls([r.film for r in rankings])
        for r in rankings:
            r.review_url = review_urls.get(r.film_id)
            r.director_url = director_urls.get(r.film_id)
        # Ties fall back to rank, except a rank sort falls back to title.
        # A stable two-pass sort keeps the tie-break ascending even when the
        # primary column is reversed.
        tiebreak = (lambda r: _sort_key(r.film.title)) if sort == 'rank' else (lambda r: r.rank)
        rankings.sort(key=tiebreak)
        rankings.sort(key=sort_keys[sort], reverse=(direction == 'desc'))
        context['rankings'] = rankings

        context['sort_headers'] = _sort_headers(self.SORT_COLUMNS, sort, direction, 'rank')
        return context


class FlexiblePage(BasePage):
    body = StreamField(
        LoadedStreamBlock(),
    )

    content_panels = BasePage.content_panels + [
        FieldPanel('body'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('body'),
    ]


# ···························································
# SNIPPETS
# ···························································

# this snippet gets registered in wagtail_hooks.py
class Film(index.Indexed, RevisionMixin, ClusterableModel):
    title = models.CharField(max_length=128)
    year = models.CharField(max_length=16, verbose_name='Year(s)')
    director = models.CharField(max_length=128, verbose_name='Director(s)')
    director_short_override = models.CharField(
        max_length=128,
        blank=True,
        verbose_name='Shortened director(s) override',
        help_text='This can be left blank if the director surname comes last '
                  'in the previous field.',
    )
    image = models.ForeignKey(
        get_image_model_string(),
        verbose_name='Image',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    _revisions = GenericRelation('wagtailcore.Revision', related_query_name='film')

    search_fields = [
        index.SearchField('title'),
        index.AutocompleteField('title'),
        index.SearchField('director'),
        index.SearchField('year'),
    ]

    panels = [
        FieldPanel('title'),
        FieldPanel('year'),
        FieldPanel('director'),
        FieldPanel('director_short_override'),
        FieldPanel('image'),
        InlinePanel('rankings', label='Ranking'),
    ]

    @property
    def director_short(self):
        return self.director_short_override or _last_names(self.director)

    @property
    def revisions(self):
        return self._revisions

    @property
    def ranking(self):
        """
        Return the film's rank on the critics' list OR a (rank, "Directors'")
        tuple if it's only on the directors' list; or None if on neither.
        """
        ranks = {r.list_id: r.rank for r in self.rankings.all()}
        if settings.BFI_250_LIST_ID in ranks:
            return ranks[settings.BFI_250_LIST_ID]
        if settings.BFI_DIRECTORS_100_LIST_ID in ranks:
            return ranks[settings.BFI_DIRECTORS_100_LIST_ID], "Directors'"
        return None

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


class ScreeningManager(models.Manager):
    def forthcoming(self):
        """
        Screenings whose screening_datetime is still in the future.
        """
        return self.filter(screening_datetime__gt=timezone.localtime().replace(tzinfo=None)).order_by('screening_datetime')


@register_snippet
class Screening(index.Indexed, RevisionMixin, ClusterableModel):
    objects = ScreeningManager()

    film = models.ForeignKey(
        Film,
        on_delete=models.PROTECT,
        related_name='screenings',
    )
    screening_datetime = models.DateTimeField(verbose_name='Screening date & time')
    theater = models.ForeignKey(
        'Theater',
        on_delete=models.PROTECT,
        related_name='screenings',
    )
    tickets_link = models.URLField(blank=True)
    is_hosted = models.BooleanField(default=False)

    _revisions = GenericRelation('wagtailcore.Revision', related_query_name='screening')

    search_fields = [
        index.RelatedFields('film', [
            index.SearchField('title'),
        ]),
        index.RelatedFields('theater', [
            index.SearchField('name'),
        ]),
    ]

    panels = [
        AutocompletePanel('film'),
        FieldPanel('screening_datetime'),
        AutocompletePanel('theater'),
        FieldPanel('tickets_link'),
        FieldPanel('is_hosted', heading='This is a hosted screening'),
    ]

    @property
    def revisions(self):
        return self._revisions

    def __str__(self):
        return f'{self.film} at {self.theater} on {self.screening_datetime}'


@register_snippet
class Theater(models.Model):
    name = models.CharField(max_length=128)
    location = models.CharField(max_length=64, blank=True)

    panels = [
        FieldPanel('name'),
        FieldPanel('location'),
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
        return f'{self.name} ({self.location})'


@register_snippet
class Quotation(index.Indexed, RevisionMixin, ClusterableModel):
    who = models.CharField(max_length=128, verbose_name='Who said it')
    what = RichTextField(verbose_name='What they said')

    _revisions = GenericRelation('wagtailcore.Revision', related_query_name='quotation')

    search_fields = [
        index.SearchField('who'),
        index.SearchField('what'),
    ]

    panels = [
        FieldPanel('who'),
        FieldPanel('what'),
    ]

    @property
    def revisions(self):
        return self._revisions

    def __str__(self):
        return self.who


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
