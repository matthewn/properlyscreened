"""
Convert the existing 'reviews' FlexiblePage into a ReviewIndexPage in place.

This keeps the same page id, path, slug, and all child ReviewPages exactly
where they are (no URL changes). It swaps only the concrete child-table rows
and repoints the shared wagtailcore_page row at the new type. Deleting the
FlexiblePage via the ORM is deliberately avoided: that would cascade to the
shared Page row and orphan the child reviews. No-ops on a database without a
'reviews' page (e.g. a fresh install).
"""

from django.db import migrations


def _swap(apps, schema_editor, slug, from_label, to_label, extra_columns):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Page = apps.get_model('wagtailcore', 'Page')
    FromPage = apps.get_model('properlyscreened', from_label)
    ToPage = apps.get_model('properlyscreened', to_label)

    page = FromPage.objects.filter(slug=slug).first()
    if page is None:
        return

    page_id = page.page_ptr_id
    columns = {'page_ptr_id': page_id, 'hero_image_id': page.hero_image_id}
    columns.update(extra_columns)
    ct, _ = ContentType.objects.get_or_create(
        app_label='properlyscreened', model=to_label.lower(),
    )

    names = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f'DELETE FROM {FromPage._meta.db_table} WHERE page_ptr_id = %s', [page_id],
        )
        cursor.execute(
            f'INSERT INTO {ToPage._meta.db_table} ({names}) VALUES ({placeholders})',
            list(columns.values()),
        )
    Page.objects.filter(pk=page_id).update(content_type=ct)


def to_review_index(apps, schema_editor):
    _swap(apps, schema_editor, 'reviews', 'FlexiblePage', 'ReviewIndexPage', {})


def to_flexible_page(apps, schema_editor):
    _swap(apps, schema_editor, 'reviews', 'ReviewIndexPage', 'FlexiblePage', {'body': '[]'})


class Migration(migrations.Migration):

    dependencies = [
        ('properlyscreened', '0025_reviewindexpage'),
    ]

    operations = [
        migrations.RunPython(to_review_index, to_flexible_page),
    ]
