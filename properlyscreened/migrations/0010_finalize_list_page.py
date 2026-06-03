import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0009_migrate_list_data"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="ranking",
            name="unique_film_per_list",
        ),
        migrations.RemoveField(
            model_name="ranking",
            name="list",
        ),
        migrations.RenameField(
            model_name="ranking",
            old_name="list_tmp",
            new_name="list",
        ),
        migrations.AlterField(
            model_name="ranking",
            name="list",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rankings",
                to="properlyscreened.list",
            ),
        ),
        migrations.AddConstraint(
            model_name="ranking",
            constraint=models.UniqueConstraint(
                fields=("film", "list"), name="unique_film_per_list"
            ),
        ),
        migrations.DeleteModel(
            name="LegacyList",
        ),
    ]
