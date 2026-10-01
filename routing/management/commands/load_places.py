import csv
import io
import zipfile
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from routing.models import Place
from routing.services.normalize import US_STATES, normalize_place_name

GAZETTEER_URL = 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/{}'
FILES = [
    (Place.KIND_PLACE, '2024_Gaz_place_national.zip'),
    (Place.KIND_COUSUB, '2024_Gaz_cousubs_national.zip'),
]


class Command(BaseCommand):
    help = 'Download the US Census Gazetteer (public domain) and load city/town centroids for offline geocoding.'

    def handle(self, *args, **options):
        cache_dir = Path(settings.BASE_DIR) / 'data' / 'gazetteer'
        cache_dir.mkdir(parents=True, exist_ok=True)

        best: dict[tuple[str, str, str], tuple[int, Place]] = {}
        for kind, filename in FILES:
            for row in self._read_rows(cache_dir / filename):
                state = row['USPS'].strip()
                if state not in US_STATES:
                    continue
                raw_name = row['NAME'].strip()
                area = int(row['ALAND'] or 0)
                lat, lon = float(row['INTPTLAT']), float(row['INTPTLONG'])
                names = {normalize_place_name(raw_name, strip_lsad=True)}
                for sep in ('-', '/'):
                    if sep in raw_name:
                        names.add(normalize_place_name(raw_name.split(sep)[0]))
                for name in names:
                    if not name:
                        continue
                    key = (state, name, kind)
                    if key not in best or area > best[key][0]:
                        best[key] = (area, Place(state=state, name=name, display_name=raw_name,
                                                 kind=kind, lat=lat, lon=lon))

        with transaction.atomic():
            Place.objects.all().delete()
            Place.objects.bulk_create([p for _, p in best.values()], batch_size=5000)
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(best)} places.'))

    def _read_rows(self, path: Path):
        if not path.exists():
            self.stdout.write(f'Downloading {path.name} ...')
            resp = requests.get(GAZETTEER_URL.format(path.name), timeout=120,
                                headers={'User-Agent': settings.HTTP_USER_AGENT})
            resp.raise_for_status()
            path.write_bytes(resp.content)
        with zipfile.ZipFile(path) as zf:
            with zf.open(zf.namelist()[0]) as fh:
                text = io.TextIOWrapper(fh, encoding='utf-8', errors='replace')
                reader = csv.DictReader(text, delimiter='\t')
                reader.fieldnames = [f.strip() for f in reader.fieldnames]
                yield from reader
