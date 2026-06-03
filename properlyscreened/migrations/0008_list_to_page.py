import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0007_alter_flexiblepage_body_alter_review_body"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
    ]

    operations = [
        # Keep the old snippet table around (as LegacyList) so the data
        # migration can copy its rows and repoint Ranking FKs before we drop it.
        migrations.RenameModel(old_name="List", new_name="LegacyList"),
        migrations.CreateModel(
            name="List",
            fields=[
                (
                    "page_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="wagtailcore.page",
                    ),
                ),
                (
                    "list_name_internal",
                    models.CharField(
                        help_text="Internal name for this list, mirrored from the page title.",
                        max_length=128,
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("wagtailcore.page",),
        ),
        # Temporary FK to the new List pages; populated by the data migration,
        # then renamed to `list` once the legacy FK is dropped.
        migrations.AddField(
            model_name="ranking",
            name="list_tmp",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rankings",
                to="properlyscreened.list",
            ),
        ),
    ]
