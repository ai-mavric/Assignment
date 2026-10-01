from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.spatial import cKDTree

from routing.models import FuelStation

from . import geo


@dataclass(frozen=True)
class StationMatch:
    station_id: int
    mile: float
    off_route: float
    price: float


class StationIndex:
    def __init__(self, ids, lats, lons, prices):
        self.ids = np.asarray(ids, dtype=np.int64)
        self.lats = np.asarray(lats, dtype=float)
        self.lons = np.asarray(lons, dtype=float)
        self.prices = np.asarray(prices, dtype=float)
        self.xyz = geo.to_unit_xyz(self.lats, self.lons) if len(self.ids) else np.empty((0, 3))

    def __len__(self):
        return len(self.ids)

    def along_route(self, route_lats, route_lons, route_miles, max_off_route_miles):
        if not len(self):
            return []
        margin = max_off_route_miles / 50.0 + 0.1
        in_box = np.flatnonzero(
            (self.lats >= route_lats.min() - margin) & (self.lats <= route_lats.max() + margin)
            & (self.lons >= route_lons.min() - margin) & (self.lons <= route_lons.max() + margin)
        )
        if not len(in_box):
            return []

        tree = cKDTree(geo.to_unit_xyz(route_lats, route_lons))
        chord, nearest = tree.query(self.xyz[in_box], distance_upper_bound=geo.miles_to_chord(max_off_route_miles))
        hit = np.isfinite(chord)
        matches = [
            StationMatch(int(self.ids[s]), float(route_miles[r]), float(geo.chord_to_miles(c)), float(self.prices[s]))
            for s, r, c in zip(in_box[hit], nearest[hit], chord[hit])
        ]
        matches.sort(key=lambda m: (m.mile, m.price))
        return matches


@lru_cache(maxsize=1)
def get_station_index() -> StationIndex:
    rows = list(FuelStation.objects.filter(lat__isnull=False).values_list('id', 'lat', 'lon', 'price'))
    if not rows:
        return StationIndex([], [], [], [])
    ids, lats, lons, prices = zip(*rows)
    return StationIndex(ids, lats, lons, [float(p) for p in prices])
