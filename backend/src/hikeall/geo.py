"""Pure geometry helpers. Points are (lat, lon) in degrees."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from typing import NamedTuple

from hikeall.models import BBox

EARTH_RADIUS_KM = 6371.0088
Point = tuple[float, float]
Segments = Sequence[Sequence[Point]]


def haversine_km(a: Point, b: Point) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def locate(line: Sequence[Point], p: Point) -> tuple[int, float]:
    """Index of the vertex of `line` nearest to `p` and its distance in metres."""
    if not line:
        raise ValueError("empty line")
    idx = min(range(len(line)), key=lambda i: haversine_km(line[i], p))
    return idx, haversine_km(line[idx], p) * 1000


def path_length_km(segments: Segments) -> float:
    return sum(haversine_km(s[i], s[i + 1]) for s in segments for i in range(len(s) - 1))


def bbox_of(segments: Segments) -> BBox:
    lats = [p[0] for s in segments for p in s]
    lons = [p[1] for s in segments for p in s]
    if not lats:
        raise ValueError("empty geometry")
    pad = 1e-6
    return BBox(
        south=min(lats) - pad, west=min(lons) - pad, north=max(lats) + pad, east=max(lons) + pad
    )


def _dist_origin_to_segment(ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
    return math.hypot(ax + t * dx, ay + t * dy)


def distance_point_to_path_km(p: Point, segments: Segments) -> float:
    """Shortest distance from p to a polyline (local equirectangular projection)."""
    cos_lat = math.cos(math.radians(p[0]))

    def project(q: Point) -> tuple[float, float]:
        return (
            math.radians(q[1] - p[1]) * cos_lat * EARTH_RADIUS_KM,
            math.radians(q[0] - p[0]) * EARTH_RADIUS_KM,
        )

    best = math.inf
    for seg in segments:
        pts = [project(q) for q in seg]
        if len(pts) == 1:
            best = min(best, math.hypot(*pts[0]))
        for (ax, ay), (bx, by) in pairwise(pts):
            best = min(best, _dist_origin_to_segment(ax, ay, bx, by))
    return best


def sample_points(segments: Segments, step_km: float = 0.2, max_points: int = 300) -> list[Point]:
    """Pick vertices roughly every `step_km`, always keeping first and last point."""
    samples: list[Point] = []
    prev: Point | None = None
    since = 0.0
    for seg in segments:
        for q in seg:
            if prev is None:
                samples.append(q)
            else:
                since += haversine_km(prev, q)
                if since >= step_km:
                    samples.append(q)
                    since = 0.0
            prev = q
    last = segments[-1][-1]
    if samples[-1] != last:
        samples.append(last)
    if len(samples) > max_points:
        idx = [round(i * (len(samples) - 1) / (max_points - 1)) for i in range(max_points)]
        samples = [samples[i] for i in idx]
    return samples


class ElevationStats(NamedTuple):
    ascent_m: float
    descent_m: float
    min_ele_m: float
    max_ele_m: float


def elevation_stats(elevations: Sequence[float], threshold_m: float = 3.0) -> ElevationStats:
    """Cumulative ascent/descent with a hysteresis threshold against DEM noise."""
    if not elevations:
        raise ValueError("no elevation values")
    ascent = descent = 0.0
    anchor = elevations[0]
    for e in elevations[1:]:
        diff = e - anchor
        if diff >= threshold_m:
            ascent += diff
            anchor = e
        elif diff <= -threshold_m:
            descent -= diff
            anchor = e
    return ElevationStats(
        round(ascent, 1), round(descent, 1), float(min(elevations)), float(max(elevations))
    )


def simplify_segments(segments: Segments, tolerance_m: float = 10.0) -> list[list[Point]]:
    """Douglas–Peucker per segment: drop vertices closer than `tolerance_m` to the simplified
    line; both endpoints of every segment are kept (spec §18.5)."""
    return [_simplify(list(segment), tolerance_m / 1000) for segment in segments]


def _simplify(points: list[Point], tolerance_km: float) -> list[Point]:
    if len(points) <= 2:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:  # iterative: long ways would exceed the recursion limit
        first, last = stack.pop()
        worst, index = -1.0, -1
        for k in range(first + 1, last):
            d = distance_point_to_path_km(points[k], [[points[first], points[last]]])
            if d > worst:
                worst, index = d, k
        if worst > tolerance_km:
            keep[index] = True
            stack.extend([(first, index), (index, last)])
    return [p for p, kept in zip(points, keep, strict=True) if kept]
