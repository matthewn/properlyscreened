from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0015_listindexpage_body"),
    ]

    operations = [
        migrations.RenameModel(old_name="List", new_name="ListPage"),
    ]
