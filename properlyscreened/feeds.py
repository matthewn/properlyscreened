from django.contrib.syndication.views import Feed

from .models import BlogPost, ReviewPage


class LatestEntriesFeed(Feed):
    title = 'Properly Screened'
    link = '/'
    description = 'Latest reviews and blog posts.'

    def items(self):
        pages = [
            *ReviewPage.objects.live().public(),
            *BlogPost.objects.live().public(),
        ]
        pages.sort(key=lambda page: page.first_published_at, reverse=True)
        return pages

    def item_title(self, item):
        return item.display_title if isinstance(item, ReviewPage) else item.title

    def item_description(self, item):
        html, is_truncated = item.excerpt()
        return html + '...' if is_truncated else html

    def item_link(self, item):
        return item.full_url

    def item_pubdate(self, item):
        return item.first_published_at
