import numpy as np

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def to_unit_xyz(lat, lon):
    lat, lon = np.radians(lat), np.radians(lon)
    return np.column_stack((np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)))


def miles_to_chord(miles):
    return 2 * np.sin(np.asarray(miles) / (2 * EARTH_RADIUS_MILES))


def chord_to_miles(chord):
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.clip(np.asarray(chord) / 2, 0, 1))


def cumulative_miles(lats, lons):
    seg = haversine_miles(lats[:-1], lons[:-1], lats[1:], lons[1:])
    return np.concatenate(([0.0], np.cumsum(seg)))


def resample(lats, lons, step_miles):
    cum = cumulative_miles(lats, lons)
    total = cum[-1]
    marks = np.append(np.arange(0.0, total, step_miles), total)
    return np.interp(marks, cum, lats), np.interp(marks, cum, lons), marks


def simplify(coords, tolerance_deg):
    coords = np.asarray(coords, dtype=float)
    n = len(coords)
    if n < 3:
        return coords
    keep = np.zeros(n, dtype=bool)
    keep[[0, -1]] = True
    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        a, b = coords[start], coords[end]
        pts = coords[start + 1:end]
        ab = b - a
        norm = np.hypot(*ab)
        if norm == 0:
            dists = np.hypot(*(pts - a).T)
        else:
            dists = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / norm
        i = int(np.argmax(dists))
        if dists[i] > tolerance_deg:
            mid = start + 1 + i
            keep[mid] = True
            stack.extend(((start, mid), (mid, end)))
    return coords[keep]
