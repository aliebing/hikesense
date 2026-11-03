"""Shared domain types."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LatLon(BaseModel):
    model_config = ConfigDict(frozen=True)

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class BBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    south: float
    west: float
    north: float
    east: float

    @model_validator(mode="after")
    def _ordered(self) -> BBox:
        if self.south >= self.north or self.west >= self.east:
            raise ValueError("bbox needs south < north and west < east")
        return self

    def contains(self, point: LatLon) -> bool:
        return self.south <= point.lat <= self.north and self.west <= point.lon <= self.east


# Box of the Black Forest region (see hikesense.regions for all regions).
BLACK_FOREST_BBOX = BBox(south=47.55, west=7.55, north=48.95, east=8.80)


class HikingTime(BaseModel):
    hours: float
    horizontal_h: float
    vertical_h: float
    formula: str


class Source(BaseModel):
    id: str
    name: str
    url: str
    license: str
    retrieved_at: date


class StageSpec(BaseModel):
    seq: int
    start_name: str
    end_name: str
    start: tuple[float, float]
    end: tuple[float, float]
    official_km: float | None = None  # published stage length, if curated; never estimated


class TrailSpec(BaseModel):
    id: str
    name: str
    kind: str
    # Walking order. An entry may be a list of ids: that group is assembled as one piece
    # (union of its route ways), e.g. a parent relation whose gaps only its child relations close.
    osm_relation_ids: list[int | list[int]]
    source: Source  # stage division
    geometry_source: Source  # line geometry (OSM, ODbL)
    stages: list[StageSpec]
    # "graph": retry a relation that cannot be chained greedily as a graph (see assemble.py)
    assemble: Literal["greedy", "graph"] = "greedy"
    # cut the line to the first stage start and last stage end (relation runs beyond the trail)
    trim: bool = False

    @property
    def relation_ids(self) -> list[int]:
        """All relation ids, groups flattened, in order."""
        return [r for e in self.osm_relation_ids for r in (e if isinstance(e, list) else [e])]


class Lodging(BaseModel):
    id: int  # OSM id; ways are negative
    name: str
    kind: str
    website: str | None = None
    lat: float
    lon: float


class Place(BaseModel):
    id: int  # OSM id; ways negative
    name: str
    kind: str  # town (incl. OSM city) | village | hamlet | peak | lake
    lat: float
    lon: float


class Poi(BaseModel):
    id: int  # OSM id; ways negative
    name: str | None = None
    kind: str  # viewpoint | peak | waterfall | food | hut | station
    lat: float
    lon: float
