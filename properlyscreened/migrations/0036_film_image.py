from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0035_remove_reviewsindexpage_body"),
    ]

    operations = [
        migrations.AddField(
            model_name="film",
            name="image",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="properlyscreened.customimage",
                verbose_name="Image",
            ),
        ),
    ]
