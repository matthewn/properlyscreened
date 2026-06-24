from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0037_move_review_images_to_film"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="reviewpage",
            name="image",
        ),
    ]
