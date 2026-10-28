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
