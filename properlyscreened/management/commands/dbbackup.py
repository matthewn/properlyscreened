"""
Back up the SQLite database to <BASE_DIR>/backups/db_DATETIME.sqlite3.

Intended for a weekly cron run. With --prune, also delete backups older
than three months, but never delete every backup.
"""

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BACKUP_RE = re.compile(r'^db_(\d{8}_\d{6})\.sqlite3$')
STAMP_FORMAT = '%Y%m%d_%H%M%S'
MAX_AGE = timedelta(days=90)


class Command(BaseCommand):
    help = 'Copy the SQLite database to backups/; optionally prune old backups.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prune', action='store_true',
            help='Also delete backups older than three months (never all).',
        )

    def handle(self, *args, **options):
        db_path = Path(settings.DATABASES['default']['NAME'])
        if not db_path.exists():
            raise CommandError(f'Database not found: {db_path}')

        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)

        stamp = datetime.now().strftime(STAMP_FORMAT)
        dest = backup_dir / f'db_{stamp}.sqlite3'
        with sqlite3.connect(db_path) as source, sqlite3.connect(dest) as target:
            source.backup(target)
        self.stdout.write(self.style.SUCCESS(f'Backed up to {dest}'))

        if options['prune']:
            self.prune(backup_dir)

    def prune(self, backup_dir):
        cutoff = datetime.now() - MAX_AGE
        backups = []
        for path in backup_dir.iterdir():
            match = BACKUP_RE.match(path.name)
            if match:
                when = datetime.strptime(match.group(1), STAMP_FORMAT)
                backups.append((when, path))

        old = [p for when, p in backups if when < cutoff]
        if len(old) == len(backups):
            self.stdout.write('Prune skipped: all backups are old; keeping them.')
            return

        for path in old:
            path.unlink()
            self.stdout.write(f'  - removed {path.name}')
        self.stdout.write(self.style.SUCCESS(f'Pruned {len(old)} old backup(s).'))
