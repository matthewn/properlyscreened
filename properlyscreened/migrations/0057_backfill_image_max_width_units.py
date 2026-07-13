import json

from django.db import migrations

# every model whose `body` StreamField can contain an ImageBlock
BODY_MODELS = [
    'HomePage',
    'ReviewPage',
    'ListsIndexPage',
    'ListPage',
    'BlogIndexPage',
    'BlogPost',
    'FlexiblePage',
    'NewsletterPage',
]


def convert(node, transform):
    """
    Recursively walk raw stream data, applying transform to every image
    block's max_width. Returns True if anything changed.
    """
    changed = False
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and 'type' in item and 'value' in item:
                if item['type'] == 'image' and isinstance(item['value'], dict):
                    old = item['value'].get('max_width')
                    new = transform(old)
                    if new != old:
                        item['value']['max_width'] = new
                        changed = True
                changed = convert(item['value'], transform) or changed
    elif isinstance(node, dict):
        for value in node.values():
            changed = convert(value, transform) or changed
    return changed


def add_percent(value):
    if value in (None, ''):
        return value
    text = str(value)
    return text if text.endswith(('%', 'px')) else text + '%'


def strip_percent(value):
    if isinstance(value, str) and value.endswith('%'):
        return value[:-1]
    return value


def apply(apps, transform):
    for name in BODY_MODELS:
        model = apps.get_model('properlyscreened', name)
        for page in model.objects.all():
            raw = list(page.body.raw_data)
            if convert(raw, transform):
                page.body = json.dumps(raw)
                page.save(update_fields=['body'])


def forwards(apps, schema_editor):
    apply(apps, add_percent)


def backwards(apps, schema_editor):
    apply(apps, strip_percent)


class Migration(migrations.Migration):

    dependencies = [
        ('properlyscreened', '0056_alter_blogindexpage_body_alter_blogpost_body_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
