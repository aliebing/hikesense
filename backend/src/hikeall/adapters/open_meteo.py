"""Open-Meteo forecast client (free, no API key): daily weather per day, never estimated."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import WeatherUnavailable
from hikeall.models import Source

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_sum,precipitation_probability_max"
)
SOURCE_ID = "open-meteo"


def weather_source(retrieved_at: date | None = None) -> Source:
    return Source(
        id=SOURCE_ID,
        name="Open-Meteo.com",
        url="https://open-meteo.com/",
        license="CC BY 4.0",
        retrieved_at=retrieved_at or date.today(),
    )


def weather_text(code: int | None) -> str | None:
    """WMO weather code (as sent by Open-Meteo) → short German text; None if unknown."""
    if code is None:
        return None
    if code == 0:
        return "Klar"
    if code == 1:
        return "Überwiegend klar"
    if code == 2:
        return "Teils bewölkt"
    if code == 3:
        return "Bedeckt"
    if code in (45, 48):
        return "Nebel"
    if 51 <= code <= 55:
        return "Nieselregen"
    if code in (56, 57):
        return "Gefrierender Nieselregen"
    if code in (61, 63, 65, 80, 81, 82):
        return "Regenschauer" if code >= 80 else "Regen"
    if code in (66, 67):
        return "Gefrierender Regen"
    if 71 <= code <= 77 or code in (85, 86):
        return "Schnee"
    if 95 <= code <= 99:
        return "Gewitter"
    return None


@dataclass(frozen=True)
class DayWeather:
    date: date
    code: int | None = None
    text: str | None = None
    t_min_c: float | None = None
    t_max_c: float | None = None
    precip_mm: float | None = None
    precip_prob_pct: float | None = None
    source_id: str = SOURCE_ID


class OpenMeteoClient:
    def __init__(self, http: httpx.Client, backoff_s: float = 1.0) -> None:
        self._http = http
        self._backoff_s = backoff_s

    def daily(self, lat: float, lon: float, start: date, end: date) -> list[DayWeather]:
        data = request_json(
            self._http, "GET", FORECAST_URL, error_cls=WeatherUnavailable,
            params={
                "latitude": lat, "longitude": lon, "daily": DAILY_FIELDS,
                "timezone": "Europe/Berlin",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
            },
            retries=2, backoff_s=self._backoff_s, rate_limit_wait_s=5.0,
        )
        try:
            daily = data["daily"]
            times = daily["time"]
        except (KeyError, TypeError) as exc:
            raise WeatherUnavailable("unexpected forecast format") from exc

        def value(key: str, i: int):
            values = daily.get(key) or []
            return values[i] if i < len(values) else None

        result = []
        try:
            for i, day in enumerate(times):
                code = value("weather_code", i)
                code = int(code) if code is not None else None
                result.append(DayWeather(
                    date=date.fromisoformat(day), code=code, text=weather_text(code),
                    t_min_c=value("temperature_2m_min", i), t_max_c=value("temperature_2m_max", i),
                    precip_mm=value("precipitation_sum", i),
                    precip_prob_pct=value("precipitation_probability_max", i),
                ))
        except (TypeError, ValueError) as exc:
            raise WeatherUnavailable("unexpected forecast format") from exc
        return result
