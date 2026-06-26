from django.db import models
from django.forms.utils import flatatt
from django.utils.html import format_html, format_html_join

from wagtail.blocks import (
    ChoiceBlock,
    IntegerBlock,
    # RawHTMLBlock,
    RichTextBlock,
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
    float_width = IntegerBlock(
        required=False,
        min_value=1,
        max_value=100,
        help_text='Width of the float, as a percentage of the container.',
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
            'link',
            'document-link',
        ],
    )
    image = ImageBlock()
    embed = EmbedBlock()
    media = MediaBlock(icon='media')
    # raw_HTML = RawHTMLBlock(required=False)
    # danger = RawHTMLBlock(label='DANGER!', required=False)
