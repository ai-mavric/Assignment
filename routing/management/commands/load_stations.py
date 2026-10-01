import csv
import json
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from routing.models import FuelStation, Place
from routing.services.normalize import normalize_place_name, normalize_state

COLUMNS = {
    'opis_id': 'opis truckstop id',
    'name': 'truckstop name',
    'address': 'address',
    'city': 'city',
    'state': 'state',
    'rack_id': 'rack id',
    'price': 'retail price',
}


class Command(BaseCommand):
    help = (
        'Load the fuel prices CSV and geocode each station to its city centroid using the Census '
        'Gazetteer (offline). Cities the Gazetteer does not know can optionally be geocoded with '
        'Nominatim (--nominatim); those results are cached in data/nominatim_cache.json.'
    )

    def add_arguments(self, parser):
        parser.add_argument('csv_path', nargs='?', default=str(settings.FUEL_PRICES_CSV))
        parser.add_argument('--nominatim', action='store_true',
                            help='Geocode unmatched cities with Nominatim (1 request/second).')

    def handle(self, *args, csv_path, nominatim, **options):
        path = Path(csv_path)
        if not path.exists():
            raise CommandError(f'CSV not found: {path}')
        if not Place.objects.exists():
            call_command('load_places', stdout=self.stdout)

        rows = self._read_csv(path)
        self.stdout.write(f'Read {len(rows)} stations from {path.name}.')

        cache_path = Path(settings.BASE_DIR) / 'data' / 'nominatim_cache.json'
        nominatim_cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

        places = self._place_lookup()
        unmatched = set()
        for row in rows:
            key = (row['state'], normalize_place_name(row['city']))
            coords = places.get(key)
            source = 'gazetteer'
            if coords is None:
                cached = nominatim_cache.get(f'{key[1]}|{key[0]}')
                if cached:
                    coords, source = tuple(cached), 'nominatim'
            if coords is None:
                unmatched.add((row['city'], row['state']))
                continue
            row['lat'], row['lon'] = coords
            row['geocode_source'] = source

        if unmatched and nominatim:
            self._geocode_with_nominatim(unmatched, nominatim_cache, cache_path)
            return self.handle(csv_path=csv_path, nominatim=False, **options)

        stations = [FuelStation(**row) for row in rows]
        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(stations, batch_size=2000)

        located = sum(1 for s in stations if s.lat is not None)
        self.stdout.write(self.style.SUCCESS(
            f'Loaded {len(stations)} stations, {located} geocoded, '
            f'{len(stations) - located} without coordinates ({len(unmatched)} unknown cities).'
        ))
        if unmatched and not nominatim:
            self.stdout.write('Re-run with --nominatim to geocode the remaining cities.')

    def _read_csv(self, path: Path) -> list[dict]:
        with path.open(encoding='utf-8-sig', newline='') as fh:
            reader = csv.DictReader(fh)
            header = {h.strip().lower(): h for h in reader.fieldnames or []}
            missing = [c for c in COLUMNS.values() if c not in header]
            if missing:
                raise CommandError(f'CSV is missing columns: {missing}. Found: {reader.fieldnames}')
            rows = []
            for line in reader:
                get = lambda field: (line[header[COLUMNS[field]]] or '').strip()
                state = normalize_state(get('state'))
                try:
                    price = Decimal(get('price'))
                except InvalidOperation:
                    continue
                if not state or price <= 0:
                    continue
                rows.append({
                    'opis_id': int(get('opis_id')),
                    'name': get('name'),
                    'address': get('address'),
                    'city': get('city'),
                    'state': state,
                    'rack_id': int(get('rack_id')) if get('rack_id').isdigit() else None,
                    'price': price,
                })
            return rows

    @staticmethod
    def _place_lookup() -> dict[tuple[str, str], tuple[float, float]]:
        lookup = {}
        for kind in (Place.KIND_COUSUB, Place.KIND_PLACE):
            for state, name, lat, lon in Place.objects.filter(kind=kind).values_list('state', 'name', 'lat', 'lon'):
                lookup[(state, name)] = (lat, lon)
        return lookup

    def _geocode_with_nominatim(self, unmatched, cache, cache_path):
        self.stdout.write(f'Geocoding {len(unmatched)} cities with Nominatim ...')
        session = requests.Session()
        session.headers['User-Agent'] = settings.HTTP_USER_AGENT
        for city, state in sorted(unmatched):
            key = f'{normalize_place_name(city)}|{state}'
            if key in cache:
                continue
            resp = session.get(f'{settings.NOMINATIM_BASE_URL}/search', timeout=settings.HTTP_TIMEOUT_SECONDS,
                               params={'city': city, 'state': state, 'countrycodes': 'us',
                                       'format': 'jsonv2', 'limit': 1})
            results = resp.json() if resp.ok else []
            cache[key] = [float(results[0]['lat']), float(results[0]['lon'])] if results else None
            self.stdout.write(f'  {city}, {state}: {cache[key]}')
            cache_path.write_text(json.dumps(cache, indent=1, sort_keys=True))
            time.sleep(1.1)
