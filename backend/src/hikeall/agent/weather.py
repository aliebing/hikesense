"""Weather for a hiking day: 14-day horizon, cached for 1 h, never estimated."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

from hikeall.adapters.open_meteo import DayWeather, OpenMeteoClient
from hikeall.errors import WeatherUnavailable

__all__ = ["DayWeather", "NoForecast", "is_rain_day", "weather_for"]

HORIZON_DAYS = 14  # days 0..14 ahead of today have a forecast; 15+ do not
CACHE_TTL_S = 3600.0
RAIN_PROB_PCT = 60
RAIN_MM = 5.0

REASON_TOO_FAR = "Noch keine Vorhersage (mehr als 14 Tage)"
REASON_PAST = "Datum liegt in der Vergangenheit"
REASON_DOWN = "Wetterdienst nicht erreichbar"
REASON_MISSING = "Für diesen Tag liegt keine Vorhersage vor"

_cache: dict[tuple[float, float, date], tuple[float, DayWeather]] = {}


@dataclass(frozen=True)
class NoForecast:
    reason: str


def weather_for(
    client: OpenMeteoClient, lat: float, lon: float, day: date, today: date
) -> DayWeather | NoForecast:
    offset = (day - today).days
    if offset < 0:
        return NoForecast(REASON_PAST)
    if offset > HORIZON_DAYS:
        return NoForecast(REASON_TOO_FAR)
    key = (round(lat, 2), round(lon, 2), day)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    try:
        days = client.daily(lat, lon, day, day)
    except WeatherUnavailable:
        return NoForecast(REASON_DOWN)  # failures are not cached
    for w in days:
        if w.date == day:
            _cache[key] = (time.monotonic(), w)
            return w
    return NoForecast(REASON_MISSING)


def is_rain_day(w: DayWeather) -> bool | None:
    """Rainy if probability >= 60 % or amount >= 5 mm; None if both are unknown."""
    if w.precip_prob_pct is None and w.precip_mm is None:
        return None
    return (w.precip_prob_pct or 0) >= RAIN_PROB_PCT or (w.precip_mm or 0) >= RAIN_MM
