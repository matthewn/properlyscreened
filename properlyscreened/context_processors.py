from functools import lru_cache

from .models import NewsletterPage


@lru_cache(maxsize=1)
def _newsletter_page():
    return NewsletterPage.objects.live().public().first()


def newsletter_page(request):
    return {'newsletter_page': _newsletter_page()}
