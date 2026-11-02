"""Import regions: Black Forest, Palatinate Forest and Lake Constance."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from hikeall.models import BBox, LatLon

RegionId = Literal["black_forest", "palatinate", "lake_constance"]

REGION_NAMES = "Schwarzwald, Bodensee und Pfälzerwald"
REGION_PHRASE = (
    "im Schwarzwald, am Bodensee (mit Schweizer und österreichischem Ufer) und im Pfälzerwald"
)


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    bbox: BBox
    countries: tuple[str, ...]
    foreign: tuple[str, ...]  # neighbouring countries a day trip of this region must not enter


REGIONS: tuple[Region, ...] = (
    Region(
        "black_forest",
        "Schwarzwald",
        BBox(south=47.55, west=7.55, north=48.95, east=8.80),
        ("DE",),
        (),
    ),
    Region(
        "palatinate",
        "Pfälzerwald",
        BBox(south=48.95, west=7.55, north=49.75, east=8.45),
        ("DE",),
        ("FR",),
    ),
    Region(
        "lake_constance",
        "Bodensee",
        BBox(south=47.40, west=8.85, north=47.95, east=9.95),
        ("DE", "CH", "AT"),
        (),
    ),
)


def get_region(region_id: str) -> Region:
    for r in REGIONS:
        if r.id == region_id:
            return r
    raise KeyError(region_id)


def region_of_line(points: Sequence[tuple[float, float]]) -> Region | None:
    """First region whose box contains all (lat, lon) points, else None (also for no points)."""
    if not points:
        return None
    for r in REGIONS:
        if all(r.bbox.contains(LatLon(lat=p[0], lon=p[1])) for p in points):
            return r
    return None
