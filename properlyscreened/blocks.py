from django.db import models
from django.forms.utils import flatatt
from django.template.loader import render_to_string
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from wagtail.blocks import (
    ChoiceBlock,
    IntegerBlock,
    # RawHTMLBlock,
    RichTextBlock,
    StaticBlock,
    StreamBlock,
    StructBlock,
    URLBlock,
)
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock
from wagtailmedia.blocks import AbstractMediaChooserBlock


class FloatChoices(models.IntegerChoices):
    # sadly, if we store NONE as 0, Wagtail adds a '-------' item to our
    # ChoiceBlock ... so, 3 it is :(
    NONE = 3
    LEFT = 1
    RIGHT = 2


class ImageBlock(StructBlock):
    image = ImageChooserBlock()
    caption = RichTextBlock(required=False, features=['bold', 'italic', 'link'])
    link = URLBlock(required=False)
    float = ChoiceBlock(
        blank=False,
        choices=FloatChoices.choices,
        default=FloatChoices.NONE,
    )
    max_width = IntegerBlock(
        required=False,
        min_value=1,
        max_value=100,
        help_text='Maximum width of the image, floated or not, as a percentage of the container (optional).',
    )

    class Meta:
        icon = 'image'
        template = 'properlyscreened/blocks/image_block.html'


class MediaBlock(AbstractMediaChooserBlock):
    def render_basic(self, value, context=None):
        if not value:
            return ''

        if value.type == 'video':
            player_code = '''
            <div>
                <video width="320" height="240" controls>
                    {0}
                    Your browser does not support the video tag.
                </video>
            </div>
            '''
        else:
            player_code = '''
            <div>
                <audio controls>
                    {0}
                    Your browser does not support the audio element.
                </audio>
            </div>
            '''

        return format_html(player_code, format_html_join(
            '\n', "<source{0}>",
            [[flatatt(s)] for s in value.sources]
        ))


class FleuronBlock(StaticBlock):
    """
    A fieldless ornament; renders the actual fleuron in the admin too.
    """

    def get_admin_text(self):
        # a SafeString makes the telepath adapter render it as HTML, not text
        return mark_safe(render_to_string('properlyscreened/blocks/fleuron.html'))


class LoadedStreamBlock(StreamBlock):
    rich_text = RichTextBlock(
        features=[
            'h3',
            'h4',
            'h5',
            'ol',
            'ul',
            'blockquote',
            'bold',
            'italic',
            'strikethrough',
            'small',
            'hr',
            'link',
            'document-link',
        ],
    )
    image = ImageBlock()
    embed = EmbedBlock()
    fleuron = FleuronBlock(
        icon='fleuron',
        label='Fleuron',
        template='properlyscreened/blocks/fleuron.html',
    )
    # media = MediaBlock(icon='media')
    # raw_HTML = RawHTMLBlock(required=False)
    # danger = RawHTMLBlock(label='DANGER!', required=False)
