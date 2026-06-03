import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from properlyscreened.models import Film, List, Ranking


# Maps a CSV ranking column to the exact List.list_name_internal it populates.
COLUMN_TO_LIST_NAME = {
    'BFI_250': 'BFI 250 (2022)',
    'BFI_100': "BFI Directors' 100 (2022)",
}


class Command(BaseCommand):
    help = 'Import Films and their Rankings from BFI.csv.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            nargs='?',
            default='BFI.csv',
            help='Path to the CSV file (default: BFI.csv in the current directory).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = options['csv_path']

        # Resolve each column to its List up front so a misnamed/missing
        # List fails loudly before we touch any data.
        lists_by_column = {}
        for column, list_name in COLUMN_TO_LIST_NAME.items():
            try:
                lists_by_column[column] = List.objects.get(list_name_internal=list_name)
            except List.DoesNotExist:
                raise CommandError(
                    f'No List found with name {list_name!r} '
                    f'(needed for the {column!r} column).'
                )

        films_seen = 0
        rankings_set = 0

        try:
            handle = open(csv_path, newline='', encoding='utf-8')
        except OSError as exc:
            raise CommandError(f'Could not open {csv_path!r}: {exc}')

        with handle:
            reader = csv.DictReader(handle)

            missing = [c for c in COLUMN_TO_LIST_NAME if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(
                    f'CSV is missing expected column(s): {", ".join(missing)}'
                )

            for row in reader:
                title = (row.get('Title') or '').strip()
                if not title:
                    continue  # skip blank lines

                year = (row.get('Year(s)') or '').strip()
                director = (row.get('Director(s)') or '').strip()

                film, _ = Film.objects.update_or_create(
                    title=title,
                    year=year,
                    defaults={'director': director},
                )
                films_seen += 1

                for column, ranking_list in lists_by_column.items():
                    raw = (row.get(column) or '').strip()
                    if not raw:
                        continue  # film isn't ranked on this list

                    try:
                        rank = int(raw)
                    except ValueError:
                        self.stderr.write(
                            f'  ! {title!r}: non-numeric {column} value {raw!r}, skipped'
                        )
                        continue

                    Ranking.objects.update_or_create(
                        film=film,
                        list=ranking_list,
                        defaults={'rank': rank},
                    )
                    rankings_set += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. {films_seen} films processed, {rankings_set} rankings set.'
        ))
