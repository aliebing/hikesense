"""Weather for a hiking day: 14-day horizon, cached for 1 h, never estimated."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

from hikeall.adapters.open_meteo import DayWeather, OpenMeteoClient
from hikeall.errors import WeatherUnavailable

__all__ = ["DayWeather", "NoForecast", "is_rain_day", "weather_for", "weather_for_days"]

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
    return weather_for_days(client, [(lat, lon, day)], today)[0]


def weather_for_days(
    client: OpenMeteoClient, wanted: list[tuple[float, float, date]], today: date
) -> list[DayWeather | NoForecast]:
    """Weather per (lat, lon, day), in order. Everything not cached is fetched in ONE request
    (all locations, from the earliest to the latest day asked for); cached 1 h per rounded
    location and day. Failures are not cached."""
    out: list[DayWeather | NoForecast | None] = []
    misses: dict[tuple[float, float], list[int]] = {}  # rounded location -> indexes in `out`
    now = time.monotonic()
    for i, (lat, lon, day) in enumerate(wanted):
        offset = (day - today).days
        if offset < 0:
            out.append(NoForecast(REASON_PAST))
            continue
        if offset > HORIZON_DAYS:
            out.append(NoForecast(REASON_TOO_FAR))
            continue
        loc = (round(lat, 2), round(lon, 2))
        hit = _cache.get((*loc, day))
        if hit and now - hit[0] < CACHE_TTL_S:
            out.append(hit[1])
            continue
        out.append(None)
        misses.setdefault(loc, []).append(i)
    if misses:
        locations = list(misses)
        days = [wanted[i][2] for idx in misses.values() for i in idx]
        try:
            series = client.daily_many(locations, min(days), max(days))
        except WeatherUnavailable:
            series = None
        for loc, per_loc in zip(locations, series or [[] for _ in locations], strict=True):
            by_date = {w.date: w for w in per_loc}
            for w in per_loc:
                _cache[(*loc, w.date)] = (time.monotonic(), w)
            for i in misses[loc]:
                if series is None:
                    out[i] = NoForecast(REASON_DOWN)
                else:
                    out[i] = by_date.get(wanted[i][2]) or NoForecast(REASON_MISSING)
    return [w if w is not None else NoForecast(REASON_MISSING) for w in out]


def is_rain_day(w: DayWeather) -> bool | None:
    """Rainy if probability >= 60 % or amount >= 5 mm; None if both are unknown."""
    if w.precip_prob_pct is None and w.precip_mm is None:
        return None
    return (w.precip_prob_pct or 0) >= RAIN_PROB_PCT or (w.precip_mm or 0) >= RAIN_MM
