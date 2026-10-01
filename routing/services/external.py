import hashlib
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache


class ExternalServiceError(Exception):
    pass


class NoRouteFound(Exception):
    pass


@dataclass
class ApiCallCounter:
    routing: int = 0
    geocoding: int = 0


_session = requests.Session()
_session.headers['User-Agent'] = settings.HTTP_USER_AGENT


def _get(url, params):
    try:
        resp = _session.get(url, params=params, timeout=settings.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise ExternalServiceError(f'{url}: {exc}') from exc
    if resp.status_code >= 500 or resp.status_code == 429:
        raise ExternalServiceError(f'{url} returned HTTP {resp.status_code}')
    try:
        return resp.json()
    except ValueError as exc:
        raise ExternalServiceError(f'{url} returned invalid JSON') from exc


def _key(prefix, *parts):
    return prefix + ':' + hashlib.sha1('|'.join(map(str, parts)).encode()).hexdigest()


def osrm_route(start, finish, counter: ApiCallCounter):
    coords = f'{start[1]:.6f},{start[0]:.6f};{finish[1]:.6f},{finish[0]:.6f}'
    key = _key('osrm', coords)
    cached = cache.get(key)
    if cached is not None:
        return cached

    counter.routing += 1
    data = _get(f'{settings.OSRM_BASE_URL}/route/v1/driving/{coords}',
                {'overview': 'full', 'geometries': 'geojson', 'alternatives': 'false', 'steps': 'false'})
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise NoRouteFound(data.get('message') or data.get('code') or 'No route found')
    route = data['routes'][0]
    result = (route['distance'] / 1609.344, route['duration'], route['geometry']['coordinates'])
    cache.set(key, result, timeout=60 * 60 * 24 * 7)
    return result


def nominatim_search(query, counter: ApiCallCounter):
    key = _key('nominatim', query.strip().lower())
    cached = cache.get(key)
    if cached is not None:
        return cached or None

    counter.geocoding += 1
    results = _get(f'{settings.NOMINATIM_BASE_URL}/search',
                   {'q': query, 'countrycodes': 'us', 'format': 'jsonv2', 'limit': 1})
    result = (float(results[0]['lat']), float(results[0]['lon']), results[0]['display_name']) if results else ()
    cache.set(key, result, timeout=60 * 60 * 24 * 30)
    return result or None
