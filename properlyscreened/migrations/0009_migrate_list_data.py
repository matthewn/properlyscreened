from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    # Use the concrete models so treebeard/Wagtail page creation behaves
    # correctly; the historical Ranking carries the temporary `list_tmp` FK.
    from django.contrib.contenttypes.models import ContentType
    from wagtail.models import Locale, Page

    from properlyscreened.models import FlexiblePage, List

    LegacyList = apps.get_model("properlyscreened", "LegacyList")
    Ranking = apps.get_model("properlyscreened", "Ranking")

    legacy_lists = list(LegacyList.objects.all())
    if not legacy_lists:
        return

    locale = Locale.get_default()
    home = Page.objects.get(depth=2)

    # A "Lists" index page parents the individual List pages, mirroring the
    # existing "Reviews" index. Reuse the stub if it already exists.
    index = home.get_children().filter(slug="lists").first()
    if index is None:
        index = FlexiblePage(
            title="Lists",
            slug="lists",
            locale=locale,
            content_type=ContentType.objects.get_for_model(FlexiblePage),
        )
        home.add_child(instance=index)
    index = Page.objects.get(pk=index.pk)

    list_ct = ContentType.objects.get_for_model(List)
    id_map = {}
    for legacy in legacy_lists:
        page = List(
            title=legacy.name,
            slug=slugify(legacy.name),
            list_name_internal=legacy.name,
            locale=locale,
            content_type=list_ct,
        )
        index.add_child(instance=page)
        id_map[legacy.pk] = page.pk
        print(f"  List {legacy.name!r}: legacy id {legacy.pk} -> page id {page.pk}")

    for ranking in Ranking.objects.all():
        ranking.list_tmp_id = id_map[ranking.list_id]
        ranking.save(update_fields=["list_tmp"])


def backwards(apps, schema_editor):
    from properlyscreened.models import List

    # Leaves the (pre-existing) "Lists" index page in place.
    List.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0008_list_to_page"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
