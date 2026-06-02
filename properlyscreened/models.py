from django import forms
from django.db import models

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.images.models import Image, AbstractImage, AbstractRendition
from wagtail.snippets.models import register_snippet

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
