from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('properlyscreened', '0020_film_latest_revision'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Review',
            new_name='ReviewPage',
        ),
    ]
