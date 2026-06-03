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


@register_snippet
class List(models.Model):
    name = models.CharField(max_length=128)

    panels = [
        FieldPanel('name'),
    ]

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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
