from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0011_alter_list_list_name_internal"),
    ]

    operations = [
        migrations.RenameField(
            model_name="list",
            old_name="list_name_internal",
            new_name="short_name",
        ),
        migrations.AlterField(
            model_name="list",
            name="short_name",
            field=models.CharField(
                help_text="Short name for the list (appears on Lists index and here in the admin).",
                max_length=128,
            ),
        ),
    ]
