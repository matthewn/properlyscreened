from django.db import migrations


def _index_page(apps):
    Page = apps.get_model("wagtailcore", "Page")
    return Page.objects.filter(slug="lists", depth=3).first()


def forwards(apps, schema_editor):
    """Convert the existing 'Lists' FlexiblePage into a ListIndexPage in place,
    keeping the same wagtailcore_page row (and its child List pages)."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    FlexiblePage = apps.get_model("properlyscreened", "FlexiblePage")

    page = _index_page(apps)
    if page is None or not FlexiblePage.objects.filter(page_ptr_id=page.pk).exists():
        return

    ct, _ = ContentType.objects.get_or_create(
        app_label="properlyscreened", model="listindexpage"
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO properlyscreened_listindexpage (page_ptr_id) VALUES (%s)",
            [page.pk],
        )
        cursor.execute(
            "DELETE FROM properlyscreened_flexiblepage WHERE page_ptr_id = %s",
            [page.pk],
        )
    Page.objects.filter(pk=page.pk).update(content_type=ct)


def backwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    ListIndexPage = apps.get_model("properlyscreened", "ListIndexPage")

    page = _index_page(apps)
    if page is None or not ListIndexPage.objects.filter(page_ptr_id=page.pk).exists():
        return

    ct, _ = ContentType.objects.get_or_create(
        app_label="properlyscreened", model="flexiblepage"
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO properlyscreened_flexiblepage (page_ptr_id, body) VALUES (%s, %s)",
            [page.pk, "[]"],
        )
        cursor.execute(
            "DELETE FROM properlyscreened_listindexpage WHERE page_ptr_id = %s",
            [page.pk],
        )
    Page.objects.filter(pk=page.pk).update(content_type=ct)


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0013_listindexpage"),
        ("contenttypes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
