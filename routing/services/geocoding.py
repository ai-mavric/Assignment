import re
from dataclasses import dataclass

from routing.models import Place

from .external import ApiCallCounter, nominatim_search
from .normalize import US_STATES, normalize_place_name, normalize_state

_LATLON = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$')

_US_BOXES = [(24.3, 49.5, -125.0, -66.8), (51.0, 71.6, -179.9, -129.9), (18.8, 22.4, -160.4, -154.7)]


class LocationError(ValueError):
    pass


@dataclass(frozen=True)
class Location:
    query: str
    lat: float
    lon: float
    label: str
    source: str


def in_usa(lat, lon):
    return any(lo_lat <= lat <= hi_lat and lo_lon <= lon <= hi_lon for lo_lat, hi_lat, lo_lon, hi_lon in _US_BOXES)


def resolve_location(query: str, counter: ApiCallCounter) -> Location:
    query = (query or '').strip()
    if not query:
        raise LocationError('Location is empty.')

    if m := _LATLON.match(query):
        lat, lon = float(m.group(1)), float(m.group(2))
        if not in_usa(lat, lon):
            raise LocationError(f'"{query}" is not inside the USA (expected "lat,lon").')
        return Location(query, lat, lon, f'{lat:.5f}, {lon:.5f}', 'coordinates')

    if place := _lookup_place(query):
        return Location(query, place.lat, place.lon, f'{place.display_name}, {place.state}', 'gazetteer')

    found = nominatim_search(query, counter)
    if not found:
        raise LocationError(f'Could not find "{query}" in the USA.')
    lat, lon, label = found
    if not in_usa(lat, lon):
        raise LocationError(f'"{query}" is not inside the USA.')
    return Location(query, lat, lon, label, 'nominatim')


def _lookup_place(query):
    parts = [p.strip() for p in query.split(',')]
    parts = [p for p in parts if p and p.lower() not in ('usa', 'us', 'united states')]
    if len(parts) != 2:
        return None
    state = normalize_state(parts[1])
    if state not in US_STATES:
        return None
    name = normalize_place_name(parts[0], strip_lsad=True)
    places = list(Place.objects.filter(state=state, name=name))
    places.sort(key=lambda p: p.kind != Place.KIND_PLACE)
    return places[0] if places else None
