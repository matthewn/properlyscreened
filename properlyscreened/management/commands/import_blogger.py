"""
Import Reviews from a Google Takeout dump of the old Blogger blog.

Reads the Atom feed of posts and, for every LIVE post, creates a ReviewPage whose
title is the film's name, links the (pre-existing) Film and a get-or-created
Theater, sets the screening date from the post date, attaches the post's hero
image from the Takeout photo album, and stores a cleaned-up version of the
post body. Draft posts are skipped. Nothing is created for Films -- a post
whose film isn't already in the database is skipped and reported.
"""

import os
import re
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

from bs4 import BeautifulSoup

from django.core.files.images import ImageFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from wagtail.models import Page
from wagtail.rich_text import RichText

from properlyscreened.models import (
    CustomImage,
    Film,
    FlexiblePage,
    ReviewPage,
    Theater,
)


ATOM = '{http://www.w3.org/2005/Atom}'
BLOGGER = '{http://schemas.google.com/blogger/2018}'

DEFAULT_FEED = 'Blogger/Blogs/Properly Screened/feed.atom'
DEFAULT_ALBUM = 'Blogger/Albums/Properly Screened'

# Post film names that don't match a Film.title even after normalization,
# mapped to the title actually stored in the database.
FILM_ALIASES = {
    'mulholland drive': 'Mulholland Dr.',
}

# Theaters the feed spells inconsistently (leading 'the', Theater/Theatre),
# keyed by lowercased feed spelling and mapped to the canonical name. Only
# these venues are rewritten; every other theater is stored as written.
THEATER_ALIASES = {
    'aero theatre': 'Aero Theatre',
    'the aero theatre': 'Aero Theatre',
    'egyptian theatre': 'Egyptian Theatre',
    'the egyptian theatre': 'Egyptian Theatre',
    'stanford theater': 'Stanford Theatre',
    'stanford theatre': 'Stanford Theatre',
}

# Tags we keep in a cleaned body; everything else is unwrapped or dropped.
# Mirrors the rich_text features available on LoadedStreamBlock.
ALLOWED_TAGS = {
    'p', 'h2', 'h3', 'h4', 'h5', 'ol', 'ul', 'li', 'blockquote',
    'b', 'strong', 'i', 'em', 'sup', 'sub', 's', 'strike', 'kbd', 'code',
    'a', 'br',
}

IMAGE_EXT_RE = r'(?:jpe?g|png|webp|gif)'


def normalize_title(value):
    """Casefold, strip accents and punctuation for forgiving title matching."""
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9 ]', '', value.lower()).strip()


def canonicalize_theater(name):
    """Map the few inconsistently-spelled venues to their canonical name (see
    THEATER_ALIASES); all other theaters are returned as written."""
    name = name.strip()
    return THEATER_ALIASES.get(name.lower(), name)


class Command(BaseCommand):
    help = 'Import Reviews from the Blogger Google Takeout dump.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--feed', default=DEFAULT_FEED,
            help=f'Path to the Atom feed (default: {DEFAULT_FEED!r}).',
        )
        parser.add_argument(
            '--album', default=DEFAULT_ALBUM,
            help=f'Path to the image album (default: {DEFAULT_ALBUM!r}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parse and report, but write nothing to the database or media.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        feed_path = options['feed']
        self.album_dir = options['album']

        if not os.path.isfile(feed_path):
            raise CommandError(f'Feed not found: {feed_path!r}')
        if not os.path.isdir(self.album_dir):
            raise CommandError(f'Album directory not found: {self.album_dir!r}')

        # Normalized-title -> Film, built once. We never create Films.
        self.films_by_norm = {normalize_title(f.title): f for f in Film.objects.all()}

        # Case-insensitive cache so repeated theater names dedupe within a run
        # (and dry-run counts match what a real run would actually create).
        self.theater_cache = {}

        parent = self._get_or_create_reviews_index()

        stats = {
            'reviews': 0, 'theaters': 0, 'images': 0,
            'skipped_draft': 0, 'skipped_nofilm': 0, 'skipped_exists': 0,
            'no_image': 0,
        }

        try:
            root = ET.parse(feed_path).getroot()
        except ET.ParseError as exc:
            raise CommandError(f'Could not parse feed: {exc}')

        for entry in root.findall(f'{ATOM}entry'):
            if self._text(entry, f'{BLOGGER}type') != 'POST':
                continue
            self._handle_post(entry, parent, stats)

        if self.dry_run:
            transaction.set_rollback(True)

        self._report(stats)

    # -- per-post -----------------------------------------------------------

    def _handle_post(self, entry, parent, stats):
        raw_title = self._text(entry, f'{ATOM}title') or ''

        if self._text(entry, f'{BLOGGER}status') != 'LIVE':
            stats['skipped_draft'] += 1
            self.stderr.write(f'  - skip (draft): {raw_title!r}')
            return

        film_name, theater_name = self._parse_title(raw_title)

        film = self._find_film(film_name)
        if film is None:
            stats['skipped_nofilm'] += 1
            self.stderr.write(f'  ! skip (no Film {film_name!r}): {raw_title!r}')
            return

        slug = slugify(film.title)
        if parent.get_children().filter(slug=slug).exists():
            stats['skipped_exists'] += 1
            self.stderr.write(f'  - skip (already imported): {film.title!r}')
            return

        content = self._text(entry, f'{ATOM}content') or ''

        theater, created = self._get_or_create_theater(theater_name)
        if created:
            stats['theaters'] += 1

        image = self._resolve_image(content, raw_title, film.title, stats)

        review = ReviewPage(
            title=film.title,
            slug=slug,
            use_manual_page_title=False,
            film=film,
            theater=theater,
            date_screened=self._post_date(entry),
            image=image,
            body=[('rich_text', RichText(self._clean_body(content)))],
            live=True,
        )

        if not self.dry_run:
            parent.add_child(instance=review)
        stats['reviews'] += 1
        self.stdout.write(f'  + {film.title} at {theater.name}')

    # -- parsing helpers ----------------------------------------------------

    @staticmethod
    def _text(element, tag):
        found = element.find(tag)
        return found.text if found is not None else None

    @staticmethod
    def _parse_title(raw_title):
        """'[Directors'] #76 The Conversation (Coppola) at The Egyptian' ->
        ('The Conversation', 'The Egyptian')."""
        s = raw_title.strip()
        s = re.sub(r'^\[[^\]]*\]\s*', '', s)   # leading [Directors'] / [snubbed]
        s = re.sub(r'^#\d+\s*', '', s)         # leading #rank
        theater = ''
        parts = re.split(r'\s+at\s+', s)
        if len(parts) > 1:
            theater = canonicalize_theater(parts[-1])
            s = ' at '.join(parts[:-1])
        film = re.sub(r'\s*\([^()]*\)\s*$', '', s).strip()  # trailing (Director)
        return film, theater

    def _find_film(self, name):
        norm = normalize_title(name)
        if norm in self.films_by_norm:
            return self.films_by_norm[norm]
        alias = FILM_ALIASES.get(norm)
        if alias is not None:
            return self.films_by_norm.get(normalize_title(alias))
        return None

    def _get_or_create_theater(self, name):
        key = name.lower()
        if key in self.theater_cache:
            return self.theater_cache[key], False
        existing = Theater.objects.filter(name__iexact=name).first()
        if existing is not None:
            self.theater_cache[key] = existing
            return existing, False
        theater = Theater(name=name) if self.dry_run else Theater.objects.create(name=name)
        self.theater_cache[key] = theater
        return theater, True

    @staticmethod
    def _post_date(entry):
        published = Command._text(entry, f'{ATOM}published')
        dt = datetime.fromisoformat(published.replace('Z', '+00:00'))
        return timezone.localtime(dt).date()

    # -- image --------------------------------------------------------------

    def _resolve_image(self, content, raw_title, film_title, stats):
        filename = self._image_filename(content)
        path = self._find_album_file(filename)
        if path is None:
            stats['no_image'] += 1
            self.stderr.write(f'  ? no image found for {raw_title!r} (looked for {filename!r})')
            return None
        if self.dry_run:
            stats['images'] += 1
            return None
        image = CustomImage(title=film_title)
        with open(path, 'rb') as fh:
            image.file = ImageFile(fh, name=os.path.basename(path))
            image.save()
        stats['images'] += 1
        return image

    @staticmethod
    def _image_filename(content):
        # Blogger image URLs look like .../s1920/<filename>; fall back to any
        # <img src>. Names are URL-encoded in the feed.
        match = re.search(rf'/s\d+(?:-[a-z]+)?/([^/"]+\.{IMAGE_EXT_RE})', content, re.I)
        if match is None:
            match = re.search(rf'src="[^"]*?/([^/"]+\.{IMAGE_EXT_RE})"', content, re.I)
        if match is None:
            return None
        return urllib.parse.unquote(match.group(1))

    def _find_album_file(self, filename):
        if not filename:
            return None
        direct = os.path.join(self.album_dir, filename)
        if os.path.isfile(direct):
            return direct
        # Takeout truncates long names: match an album file whose stem is a
        # prefix of the wanted stem (same extension).
        stem, ext = os.path.splitext(filename)
        ext = ext.lower()
        for name in os.listdir(self.album_dir):
            if name.endswith('.json'):
                continue
            f_stem, f_ext = os.path.splitext(name)
            if f_ext.lower() == ext and len(f_stem) >= 12 and stem.startswith(f_stem):
                return os.path.join(self.album_dir, name)
        return None

    # -- body cleaning ------------------------------------------------------

    @staticmethod
    def _clean_body(content):
        soup = BeautifulSoup(content, 'html.parser')

        # Drop the hero-image container(s) and any stray images.
        for sep in soup.select('div.separator'):
            sep.decompose()
        for img in soup.find_all('img'):
            img.decompose()

        # Unwrap disallowed tags (div/span/...), strip attributes elsewhere.
        for tag in soup.find_all(True):
            if tag.name not in ALLOWED_TAGS:
                tag.unwrap()
            elif tag.name == 'a':
                tag.attrs = {'href': tag['href']} if tag.get('href') else {}
            else:
                tag.attrs = {}

        # Remove now-empty block elements (e.g. Blogger's leading <p></p>).
        for tag in soup.find_all(['p', 'li', 'blockquote', 'h2', 'h3', 'h4', 'h5']):
            if not tag.get_text(strip=True) and not tag.find('br'):
                tag.decompose()

        return str(soup).strip()

    # -- tree + reporting ---------------------------------------------------

    def _get_or_create_reviews_index(self):
        root = Page.objects.filter(depth=1).first()
        if root is None:
            raise CommandError('No root page found; the page tree is empty.')
        existing = root.get_children().filter(slug='reviews').first()
        if existing is not None:
            return existing.specific
        index = FlexiblePage(title='Reviews', slug='reviews', body=[])
        if not self.dry_run:
            root.add_child(instance=index)
        return index

    def _report(self, stats):
        prefix = 'DRY RUN -- nothing written.\n' if self.dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Done. '
            f'{stats["reviews"]} reviews, {stats["theaters"]} theaters, '
            f'{stats["images"]} images. '
            f'Skipped: {stats["skipped_draft"]} draft, '
            f'{stats["skipped_nofilm"]} no-film, '
            f'{stats["skipped_exists"]} already-imported; '
            f'{stats["no_image"]} without an image.'
        ))
