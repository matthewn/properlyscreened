from django.db import migrations


def _home_page(apps):
    Page = apps.get_model("wagtailcore", "Page")
    return Page.objects.filter(slug="home-page", depth=2).first()


def _convert(apps, schema_editor, from_table, to_table, to_model):
    """Move the home page's row between MTI child tables in place, carrying the
    body across and keeping the same wagtailcore_page row (the site root)."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")

    page = _home_page(apps)
    if page is None:
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"SELECT body FROM {from_table} WHERE page_ptr_id = %s", [page.pk]
        )
        row = cursor.fetchone()
        if row is None:
            return
        body = row[0]
        cursor.execute(
            f"INSERT INTO {to_table} (page_ptr_id, body) VALUES (%s, %s)",
            [page.pk, body],
        )
        cursor.execute(
            f"DELETE FROM {from_table} WHERE page_ptr_id = %s", [page.pk]
        )
    ct, _ = ContentType.objects.get_or_create(
        app_label="properlyscreened", model=to_model
    )
    Page.objects.filter(pk=page.pk).update(content_type=ct)


def forwards(apps, schema_editor):
    _convert(
        apps, schema_editor,
        from_table="properlyscreened_flexiblepage",
        to_table="properlyscreened_homepage",
        to_model="homepage",
    )


def backwards(apps, schema_editor):
    _convert(
        apps, schema_editor,
        from_table="properlyscreened_homepage",
        to_table="properlyscreened_flexiblepage",
        to_model="flexiblepage",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0017_homepage"),
        ("contenttypes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
