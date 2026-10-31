"""Structured hiking/running request: what the user wants, as checkable fields."""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from hikeall.models import BBox

ConstraintKind = Literal["roundtrip", "length_km", "ascent_m", "duration_h", "radius_km"]
Intent = Literal["day_hike", "multiday", "knowledge", "change", "events", "groups", "other"]
Activity = Literal["hike", "run"]
Mode = Literal["prefer", "avoid"]

DEFAULT_RADIUS_KM = 15.0
MAX_PREFERENCES = 10
MIN_DAYS = 1
MAX_DAYS = 14
DEFAULT_DAY_KM = 15.0  # daily target without a wish (shown in the echo)
DEFAULT_START_TIME = time(9, 0)  # start time without a wish (shown in the echo)


class Constraint(BaseModel):
    kind: ConstraintKind
    min: float | None = None
    max: float | None = None
    required: bool | None = None
    approx: float | None = None  # "8 km" without a bound word: the value the band is built around

    @model_validator(mode="after")
    def _check(self) -> Constraint:
        if self.kind == "roundtrip":
            if self.required is None:
                raise ValueError("roundtrip needs required")
        elif self.min is None and self.max is None:
            raise ValueError(f"{self.kind} needs min or max")
        return self


class Preference(BaseModel):
    tag_id: str
    mode: Mode
    weight: int = Field(default=3, ge=1, le=5)


class ResolvedStart(BaseModel):
    kind: Literal["place", "area"]
    tag_id: str
    label: str
    lat: float | None = None
    lon: float | None = None
    bbox: BBox | None = None


class DayChange(BaseModel):
    """ "Tag 3 kürzer": one day of the previous multi-day plan gets shorter or longer."""

    day: int = Field(ge=MIN_DAYS, le=MAX_DAYS)
    change: Literal["shorter", "longer"]


class HikeRequest(BaseModel):
    intent: Intent
    activity: Activity = "hike"
    start_text: str | None = None
    start: ResolvedStart | None = None
    constraints: list[Constraint] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list, max_length=MAX_PREFERENCES)
    pace_min_per_km: float | None = None
    unmatched: list[str] = Field(default_factory=list)
    question: str | None = None
    # multi-day (values only when the user wrote them, R27; defaults stay None and show in echo)
    trail_id: str | None = None
    trail_assumed: bool = False  # "Westweg" without a variant: west variant assumed
    days: int | None = Field(default=None, ge=MIN_DAYS, le=MAX_DAYS)
    day_km: float | None = None
    start_date: date | None = None
    start_time: time | None = None
    day_change: DayChange | None = None
    # numbers (and a roundtrip yes/no) the model filled in that the user never wrote (discarded, R27);
    # for the log only
    discarded_model_numbers: int = Field(default=0, exclude=True)


class Clarify(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)


Understood = HikeRequest | Clarify


class RawWish(BaseModel):
    """A wish as the user phrased it; mapped to a vocabulary tag in code."""

    text: str
    mode: Mode = "prefer"
    weight: int = 3


class RawRequest(BaseModel):
    """Model output: like HikeRequest, but place and wishes are still free text."""

    intent: Intent
    activity: Activity | None = None
    start_text: str | None = None
    roundtrip: bool | None = None
    length_km_min: float | None = None
    length_km_max: float | None = None
    ascent_m_min: float | None = None
    ascent_m_max: float | None = None
    duration_h_min: float | None = None
    duration_h_max: float | None = None
    # a single value without a bound word ("8 km"); the code turns it into a visible band
    length_km_approx: float | None = None
    ascent_m_approx: float | None = None
    duration_h_approx: float | None = None
    radius_km_max: float | None = None
    pace_min_per_km: float | None = None
    trail_text: str | None = None  # long-distance trail as named ("Westweg", "Westweg Ostvariante")
    days: int | None = None
    day_km: float | None = None  # daily target in km ("18 km pro Tag")
    start_date: str | None = None  # ISO, only what the user wrote; checked against the message
    start_time: str | None = None  # "HH:MM", only what the user wrote; checked as well
    day_change_day: int | None = None  # "Tag 3 kürzer" -> 3
    day_change_direction: Literal["shorter", "longer"] | None = None
    wishes: list[RawWish] = Field(default_factory=list)
    question: str | None = None
