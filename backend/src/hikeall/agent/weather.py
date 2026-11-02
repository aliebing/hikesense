"""Weather for a hiking day: 14-day horizon, cached for 1 h, never estimated."""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from hikeall.adapters.open_meteo import DayWeather, OpenMeteoClient, weather_text
from hikeall.errors import WeatherUnavailable
from hikeall.numfmt import Lang

__all__ = [
    "DayWeather",
    "NoForecast",
    "WeatherWish",
    "forecast_range",
    "is_rain_day",
    "localize",
    "matches",
    "reason_text",
    "score",
    "weather_for",
    "weather_for_days",
]

HORIZON_DAYS = 14  # days 0..14 ahead of today have a forecast; 15+ do not
CACHE_TTL_S = 3600.0
RAIN_PROB_PCT = 60
RAIN_MM = 5.0

# Thresholds for weather wishes (our decision, documented here; all inclusive limits).
WeatherWish = Literal["fine", "dry", "snow"]
FINE_MAX_MM = 0.5  # "fine": at most this much precipitation ...
FINE_MAX_PROB = 30  # ... at most this probability (%) ...
FINE_CODES = frozenset({0, 1, 2, 3})  # ... and clear to overcast (no fog, no precipitation)
DRY_MAX_MM = 1.0  # "dry": at most this much precipitation ...
DRY_MAX_PROB = 40  # ... and at most this probability (%)
SNOW_MIN_CM = 1.0  # "snow": at least this much snowfall ...
SNOW_CODES = frozenset({71, 73, 75, 77, 85, 86})  # ... or a snow weather code

REASON_TOO_FAR = "Noch keine Vorhersage (mehr als 14 Tage)"
REASON_PAST = "Datum liegt in der Vergangenheit"
REASON_DOWN = "Wetterdienst nicht erreichbar"
REASON_MISSING = "Für diesen Tag liegt keine Vorhersage vor"

ReasonCode = Literal["not_yet", "past", "unavailable", "missing", "no_place"]

REASON_TEXTS: dict[ReasonCode, dict[Lang, str]] = {
    "not_yet": {"de": REASON_TOO_FAR, "en": "No forecast yet (more than 14 days ahead)"},
    "past": {"de": REASON_PAST, "en": "The date is in the past"},
    "unavailable": {"de": REASON_DOWN, "en": "Weather service not reachable"},
    "missing": {"de": REASON_MISSING, "en": "There is no forecast for this day"},
    "no_place": {
        "de": "Ort für die Vorhersage unbekannt",
        "en": "Place for the forecast unknown",
    },
}

_cache: dict[tuple[float, float, date], tuple[float, DayWeather]] = {}


@dataclass(frozen=True)
class NoForecast:
    """No forecast for a day: `reason` is the text (German unless localised), `code` the reason
    for code (the web checks it, not the text). The code is not part of equality."""

    reason: str
    code: ReasonCode = field(default="unavailable", compare=False)


def reason_text(code: ReasonCode, lang: Lang = "de") -> str:
    return REASON_TEXTS[code][lang]


def no_forecast(code: ReasonCode, lang: Lang = "de") -> NoForecast:
    return NoForecast(reason_text(code, lang), code)


def localize(w: DayWeather | NoForecast, lang: Lang) -> DayWeather | NoForecast:
    """The forecast with its words in the reply language (the cache holds German words; German
    stays as it is). The weather code, not the cached text, decides the English word."""
    if lang == "de":
        return w
    if isinstance(w, NoForecast):
        return no_forecast(w.code, lang)
    return dataclasses.replace(w, text=weather_text(w.code, lang))


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
            out.append(NoForecast(REASON_PAST, "past"))
            continue
        if offset > HORIZON_DAYS:
            out.append(NoForecast(REASON_TOO_FAR, "not_yet"))
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
                    out[i] = NoForecast(REASON_DOWN, "unavailable")
                else:
                    out[i] = by_date.get(wanted[i][2]) or NoForecast(REASON_MISSING, "missing")
    return [w if w is not None else NoForecast(REASON_MISSING, "missing") for w in out]


def is_rain_day(w: DayWeather) -> bool | None:
    """Rainy if probability >= 60 % or amount >= 5 mm; None if both are unknown."""
    if w.precip_prob_pct is None and w.precip_mm is None:
        return None
    return (w.precip_prob_pct or 0) >= RAIN_PROB_PCT or (w.precip_mm or 0) >= RAIN_MM


def matches(w: DayWeather, wish: WeatherWish) -> bool | None:
    """Does the day fit the wish? None if a value needed for the decision is missing."""
    if wish == "fine":
        if w.code is None or w.precip_mm is None or w.precip_prob_pct is None:
            return None
        return (
            w.code in FINE_CODES
            and w.precip_mm <= FINE_MAX_MM
            and w.precip_prob_pct <= FINE_MAX_PROB
        )
    if wish == "dry":
        if w.precip_mm is None or w.precip_prob_pct is None:
            return None
        return w.precip_mm <= DRY_MAX_MM and w.precip_prob_pct <= DRY_MAX_PROB
    # snow: positive evidence from either value is enough; otherwise both must be known
    if (w.snowfall_cm is not None and w.snowfall_cm >= SNOW_MIN_CM) or (
        w.code is not None and w.code in SNOW_CODES
    ):
        return True
    if w.snowfall_cm is None or w.code is None:
        return None
    return False


def score(w: DayWeather, wish: WeatherWish) -> float:
    """Ranking for "best days", higher is better. Missing values count as worst for the wish."""
    if wish == "snow":
        return w.snowfall_cm if w.snowfall_cm is not None else 0.0
    # fine/dry: less precipitation first, then lower probability (prob is at most 100)
    mm = w.precip_mm if w.precip_mm is not None else 100.0
    prob = w.precip_prob_pct if w.precip_prob_pct is not None else 100.0
    return -(mm + prob / 1000.0)


def forecast_range(
    client: OpenMeteoClient, points: list[tuple[float, float]], today: date
) -> list[list[DayWeather]] | NoForecast:
    """Forecast for today..today+14 per point, in ONE request; cached 1 h like `weather_for`.
    Failures are not cached."""
    end = today + timedelta(days=HORIZON_DAYS)
    days = [today + timedelta(days=i) for i in range(HORIZON_DAYS + 1)]
    locs = [(round(lat, 2), round(lon, 2)) for lat, lon in points]
    now = time.monotonic()

    def cached(loc: tuple[float, float]) -> list[DayWeather] | None:
        hits = [_cache.get((*loc, d)) for d in days]
        if all(h and now - h[0] < CACHE_TTL_S for h in hits):
            return [h[1] for h in hits if h]
        return None

    result = [cached(loc) for loc in locs]
    missing = [i for i, r in enumerate(result) if r is None]
    if missing:
        try:
            series = client.daily_many([points[i] for i in missing], today, end)
        except WeatherUnavailable:
            return no_forecast("unavailable")
        t = time.monotonic()
        for i, per_loc in zip(missing, series, strict=True):
            for w in per_loc:
                _cache[(*locs[i], w.date)] = (t, w)
            result[i] = per_loc
    return [r or [] for r in result]
