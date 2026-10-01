import hashlib
import time

import numpy as np
from django.conf import settings
from django.core.cache import cache

from routing.models import FuelStation

from . import geo
from .external import ApiCallCounter, osrm_route
from .geocoding import resolve_location
from .optimizer import Candidate, plan_fuel_stops
from .stations import get_station_index

RESAMPLE_STEP_MILES = 0.5
MAP_SIMPLIFY_TOLERANCE_DEG = 0.0005
PLAN_CACHE_SECONDS = 60 * 60


def plan_cache_key(start: str, finish: str) -> str:
    raw = f'{start.strip().lower()}|{finish.strip().lower()}'
    return 'plan:' + hashlib.sha1(raw.encode()).hexdigest()


def get_trip_plan(start: str, finish: str) -> dict:
    t0 = time.perf_counter()
    key = plan_cache_key(start, finish)
    plan = cache.get(key)
    if plan is None:
        plan = build_trip_plan(start, finish)
        cache.set(key, plan, timeout=PLAN_CACHE_SECONDS)
        return plan
    meta = {**plan['meta'], 'cached': True, 'routing_api_calls': 0, 'geocoding_api_calls': 0,
            'elapsed_ms': round((time.perf_counter() - t0) * 1000, 1)}
    return {**plan, 'meta': meta}


def build_trip_plan(start: str, finish: str) -> dict:
    t0 = time.perf_counter()
    counter = ApiCallCounter()
    tank_range = settings.VEHICLE_RANGE_MILES
    mpg = settings.VEHICLE_MPG

    origin = resolve_location(start, counter)
    destination = resolve_location(finish, counter)
    route_miles, duration_s, coords = osrm_route((origin.lat, origin.lon), (destination.lat, destination.lon), counter)

    coords = np.asarray(coords, dtype=float)
    lats, lons, marks = geo.resample(coords[:, 1], coords[:, 0], RESAMPLE_STEP_MILES)
    if marks[-1] > 0:
        marks = marks * (route_miles / marks[-1])

    matches = get_station_index().along_route(lats, lons, marks, settings.MAX_STATION_DETOUR_MILES)
    candidates = [Candidate(m.station_id, m.mile, m.off_route, m.price) for m in matches]
    result = plan_fuel_stops(route_miles, candidates, tank_range, mpg,
                             price_tolerance=settings.FUEL_PRICE_TOLERANCE,
                             min_purchase=settings.MIN_PURCHASE_GALLONS * mpg)

    stations = FuelStation.objects.in_bulk([s.candidate.key for s in result.stops])
    fuel_stops = []
    for n, stop in enumerate(result.stops, start=1):
        c, st = stop.candidate, stations[stop.candidate.key]
        fuel_stops.append({
            'stop_number': n,
            'station_id': st.id,
            'opis_id': st.opis_id,
            'name': st.name,
            'address': st.address,
            'city': st.city,
            'state': st.state,
            'lat': st.lat,
            'lon': st.lon,
            'price_per_gallon': round(c.price, 3),
            'route_mile': round(c.mile, 1),
            'distance_from_route_miles': round(c.off_route, 1),
            'fuel_on_arrival_gallons': round(stop.fuel_on_arrival / mpg, 2),
            'gallons_purchased': round(stop.gallons, 2),
            'cost': round(stop.gallons * c.price, 2),
        })

    simplified = geo.simplify(coords, MAP_SIMPLIFY_TOLERANCE_DEG)
    return {
        'start': _location_dict(origin),
        'finish': _location_dict(destination),
        'route': {
            'distance_miles': round(route_miles, 1),
            'duration_hours': round(duration_s / 3600, 2),
            'geometry': {'type': 'LineString', 'coordinates': np.round(simplified, 5).tolist()},
        },
        'fuel_stops': fuel_stops,
        'summary': {
            'total_fuel_cost': round(result.total_cost, 2),
            'gallons_purchased': round(result.gallons_purchased, 2),
            'number_of_stops': len(fuel_stops),
            'total_distance_miles': round(result.driven_miles, 1),
            'total_fuel_used_gallons': round(result.driven_miles / mpg, 2),
            'vehicle_range_miles': tank_range,
            'vehicle_mpg': mpg,
            'assumptions': (
                f'Vehicle starts with a full tank ({tank_range} mi / {tank_range / mpg:.0f} gal) and '
                f'gets {mpg} mpg. total_fuel_cost is the money spent at the fuel stops. Stations up to '
                f'{settings.MAX_STATION_DETOUR_MILES} mi off the route are considered; the detour is '
                'counted against range.'
            ),
        },
        'meta': {
            'routing_api_calls': counter.routing,
            'geocoding_api_calls': counter.geocoding,
            'stations_considered': len(candidates),
            'cached': False,
            'elapsed_ms': round((time.perf_counter() - t0) * 1000, 1),
        },
    }


def _location_dict(loc):
    return {'query': loc.query, 'label': loc.label, 'lat': round(loc.lat, 6), 'lon': round(loc.lon, 6),
            'geocoded_by': loc.source}
