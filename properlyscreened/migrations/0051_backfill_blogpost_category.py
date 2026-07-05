from django.db import migrations


def set_default_category(apps, schema_editor):
    BlogPost = apps.get_model('properlyscreened', 'BlogPost')
    BlogPost.objects.filter(category='').update(category='theaters')


class Migration(migrations.Migration):

    dependencies = [
        ('properlyscreened', '0050_blogpost_category'),
    ]

    operations = [
        migrations.RunPython(set_default_category, migrations.RunPython.noop),
    ]
