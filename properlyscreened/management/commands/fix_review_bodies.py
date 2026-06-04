"""
Re-wrap malformed imported ReviewPage bodies so every paragraph sits in a <p>.

Some Blogger imports stored prose with <br> (or bare newlines) as paragraph
separators and only partially wrapped in <p>, so the leading paragraph(s)
rendered outside any <p>. This rewrites each affected rich_text block: loose,
<br>-separated runs become <p> paragraphs, while existing block elements
(p, blockquote, lists, headings) are left untouched. Only blocks that actually
change are rewritten, and the command is idempotent.
"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from django.core.management.base import BaseCommand
from django.db import transaction

from wagtail.rich_text import RichText

from properlyscreened.models import ReviewPage


# Block-level tags that already stand on their own and must not be wrapped.
BLOCK_TAGS = {'p', 'blockquote', 'ul', 'ol', 'h2', 'h3', 'h4', 'h5'}


def needs_fix(html):
    """True if any prose sits outside a block element (loose text or a <br>)."""
    for node in BeautifulSoup(html, 'html.parser').contents:
        if isinstance(node, Tag) and node.name not in BLOCK_TAGS:
            return True
        if isinstance(node, NavigableString) and node.strip():
            return True
    return False


def normalize(html):
    """Wrap <br>-separated prose in <p>, leaving existing block elements as-is."""
    soup = BeautifulSoup(html, 'html.parser')
    out = BeautifulSoup('', 'html.parser')
    run = []

    def flush():
        nodes, run[:] = run[:], []
        if not any(n.get_text(strip=True) if isinstance(n, Tag) else n.strip()
                   for n in nodes):
            return
        p = out.new_tag('p')
        for n in nodes:
            p.append(n)
        out.append(p)

    for node in list(soup.contents):
        if isinstance(node, Tag) and node.name in BLOCK_TAGS:
            flush()
            if node.get_text(strip=True):   # drop empties like <p><br/></p>
                out.append(node)
        elif isinstance(node, Tag) and node.name == 'br':
            flush()
        else:
            run.append(node)
    flush()

    result = str(out)
    result = re.sub(r'<p>[ \t\r\n\f]+', '<p>', result)   # tidy edges, keep \xa0
    return re.sub(r'[ \t\r\n\f]+</p>', '</p>', result)


class Command(BaseCommand):
    help = 'Wrap malformed imported ReviewPage paragraphs in <p>.'

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

        fixed = 0
        for page in pages.order_by('id'):
            new_body, changed = [], False
            for block in page.body:
                value = block.value
                if block.block_type == 'rich_text' and needs_fix(str(value)):
                    value = RichText(normalize(str(value)))
                    changed = True
                new_body.append((block.block_type, value))

            if not changed:
                continue

            fixed += 1
            self.stdout.write(f'  + [{page.id}] {page.display_title}')
            if not dry_run:
                page.body = new_body
                page.save_revision().publish()

        if dry_run:
            transaction.set_rollback(True)
        prefix = 'DRY RUN -- nothing written.\n' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Done. {fixed} review(s) rewritten.'
        ))
