"""Shared domain types."""

from __future__ import annotations

from datetime import date

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


# Global import area (Black Forest only).
BLACK_FOREST_BBOX = BBox(south=47.55, west=7.55, north=48.95, east=8.75)


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
    osm_relation_ids: list[int]
    source: Source  # stage division
    geometry_source: Source  # line geometry (OSM, ODbL)
    stages: list[StageSpec]


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
    kind: str  # town | village | hamlet | peak | lake
    lat: float
    lon: float


class Poi(BaseModel):
    id: int  # OSM id; ways negative
    name: str | None = None
    kind: str  # viewpoint | peak | waterfall | food | hut | station
    lat: float
    lon: float
