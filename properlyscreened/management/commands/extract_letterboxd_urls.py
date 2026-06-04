"""
Move manual Letterboxd links out of ReviewPage bodies into letterboxd_url.

The Blogger import left a "<Film> on Letterboxd" link in each review body.
This pulls the href into the dedicated letterboxd_url field and removes the
link from the body, dropping its containing <p> if nothing else is left.
Idempotent: a review whose body has no Letterboxd link is skipped.
"""

from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.db import transaction

from wagtail.rich_text import RichText

from properlyscreened.models import ReviewPage


def extract(html):
    """Return (url, new_html) with the Letterboxd link removed, or (None, html)."""
    soup = BeautifulSoup(html, 'html.parser')
    links = [a for a in soup.find_all('a', href=True) if 'letterboxd.com' in a['href']]
    if not links:
        return None, html
    url = links[0]['href']
    for a in links:
        parent = a.parent
        a.decompose()
        if parent.name == 'p' and not parent.get_text(strip=True) and not parent.find('img'):
            parent.decompose()
    return url, str(soup)


class Command(BaseCommand):
    help = 'Move Letterboxd links from review bodies into letterboxd_url.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change, but write nothing.',
        )
        parser.add_argument(
            '--ids', nargs='+', type=int, metavar='ID',
            help='Limit to these ReviewPage ids (default: all reviews).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        pages = ReviewPage.objects.all()
        if options['ids']:
            pages = pages.filter(id__in=options['ids'])

        moved = 0
        for page in pages.order_by('id'):
            url, new_body = None, []
            for block in page.body:
                value = block.value
                if block.block_type == 'rich_text' and url is None:
                    found, fixed_html = extract(str(value))
                    if found:
                        url, value = found, RichText(fixed_html)
                new_body.append((block.block_type, value))

            if url is None:
                continue

            moved += 1
            self.stdout.write(f'  + [{page.id}] {page.display_title} -> {url}')
            if not dry_run:
                page.letterboxd_url = url
                page.body = new_body
                page.save_revision().publish()

        if dry_run:
            transaction.set_rollback(True)
        prefix = 'DRY RUN -- nothing written.\n' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Done. {moved} link(s) moved.'
        ))
