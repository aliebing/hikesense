"""Ascent/descent and elevation profile for a line. Missing elevations are never guessed."""

from __future__ import annotations

from datetime import date
from itertools import pairwise
from typing import NamedTuple, Protocol

from hikeall.geo import Point, haversine_km
from hikeall.models import LatLon, Source

SMOOTH_WINDOW = 5
MAX_PROFILE_POINTS = 300

ELEVATION_SOURCE_ID = "copernicus-glo30"


def elevation_source() -> Source:
    """Where every Hm figure comes from in Plan 1 (adapters.dem.CopernicusDem).

    Free to use with attribution; the importers store it like the other sources."""
    return Source(
        id=ELEVATION_SOURCE_ID,
        name="Copernicus DEM GLO-30",
        url="https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model",
        license=(
            "© DLR e.V. 2010–2014 und © Airbus Defence and Space GmbH 2014–2018, "
            "bereitgestellt unter COPERNICUS von der Europäischen Union und ESA"
        ),
        retrieved_at=date.today(),
    )


class ElevationProvider(Protocol):
    def elevations(self, points: list[LatLon]) -> list[float | None]: ...


class ElevationStats(NamedTuple):
    ascent_m: int
    descent_m: int
    profile: list[tuple[float, float]]  # (distance_km, elevation_m)


def _resample(line: list[Point], step_m: float) -> list[tuple[Point, float]]:
    """Points every step_m along the line with their distance (km) from the start."""
    out = [(line[0], 0.0)]
    travelled = 0.0  # km at line[i]
    next_at = step_m / 1000
    for a, b in pairwise(line):
        seg = haversine_km(a, b)
        while seg > 0 and next_at <= travelled + seg:
            f = (next_at - travelled) / seg
            out.append(((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), next_at))
            next_at += step_m / 1000
        travelled += seg
    if out[-1][1] < travelled - 1e-9:
        out.append((line[-1], travelled))
    return out


def _smooth(values: list[float], window: int) -> list[float]:
    half = window // 2
    return [
        sum(values[max(0, i - half) : i + half + 1]) / len(values[max(0, i - half) : i + half + 1])
        for i in range(len(values))
    ]


def elevation_stats(
    line: list[Point], provider: ElevationProvider, step_m: float = 50
) -> ElevationStats:
    if len(line) < 2:
        raise ValueError("line needs at least two points")
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    samples = _resample(line, step_m)
    raw = provider.elevations([LatLon(lat=p[0], lon=p[1]) for p, _ in samples])
    if len(raw) != len(samples) or any(v is None for v in raw):
        raise ValueError("elevation missing for part of the line")
    smooth = _smooth([float(v) for v in raw if v is not None], SMOOTH_WINDOW)
    ascent = descent = 0.0
    for a, b in pairwise(smooth):
        if b > a:
            ascent += b - a
        else:
            descent += a - b
    profile = [(round(d, 3), round(e, 1)) for (_, d), e in zip(samples, smooth, strict=True)]
    if len(profile) > MAX_PROFILE_POINTS:
        n = MAX_PROFILE_POINTS
        profile = [profile[round(i * (len(profile) - 1) / (n - 1))] for i in range(n)]
    return ElevationStats(round(ascent), round(descent), profile)
