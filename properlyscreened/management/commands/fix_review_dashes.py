"""
Replace imported em-dash artifacts ("---") with "--" in ReviewPage bodies.

The Blogger import migrated em dashes to triple hyphens. This rewrites each
affected rich_text block, swapping every "---" for "--" (a later templatetag
turns those into real em dashes). Only changed blocks are rewritten, and the
command is idempotent.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from wagtail.rich_text import RichText

from properlyscreened.models import ReviewPage


class Command(BaseCommand):
    help = 'Replace "---" with "--" in imported ReviewPage bodies.'

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
                if block.block_type == 'rich_text' and '---' in str(value):
                    value = RichText(str(value).replace('---', '--'))
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
