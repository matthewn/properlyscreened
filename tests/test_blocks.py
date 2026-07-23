import json

import pytest
from django.core.exceptions import ValidationError
from wagtail.blocks.base import get_error_json_data

from properlyscreened.blocks import ImageBlock


class TestImageBlockMaxWidthError:
    def test_invalid_max_width_error_serializes_to_json(self):
        # A bare number (no % or px suffix) fails the RegexBlock. Wagtail then
        # serializes the block error to JSON, which percent-formats the message.
        # A literal '%' in the message must be escaped as '%%' or this raises
        # ValueError: unsupported format character ')'.
        max_width = ImageBlock().child_blocks['max_width']
        try:
            max_width.clean('50')
        except ValidationError as error:
            json.dumps(get_error_json_data(error))
        else:
            pytest.fail('expected a ValidationError for invalid max_width')
