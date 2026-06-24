from django.db import migrations


def copy_images_to_film(apps, schema_editor):
    """Copy each ReviewPage's image onto its Film (one review per film)."""
    ReviewPage = apps.get_model("properlyscreened", "ReviewPage")
    for review in ReviewPage.objects.filter(image__isnull=False).select_related("film"):
        film = review.film
        film.image_id = review.image_id
        film.save(update_fields=["image"])


def clear_film_images(apps, schema_editor):
    """Reverse: copy each Film's image back onto its ReviewPage(s)."""
    Film = apps.get_model("properlyscreened", "Film")
    for film in Film.objects.filter(image__isnull=False):
        film.reviews.update(image=film.image_id)


class Migration(migrations.Migration):

    dependencies = [
        ("properlyscreened", "0036_film_image"),
    ]

    operations = [
        migrations.RunPython(copy_images_to_film, clear_film_images),
    ]
