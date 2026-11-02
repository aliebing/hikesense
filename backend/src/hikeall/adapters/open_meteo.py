"""Open-Meteo forecast client (free, no API key): daily weather per day, never estimated."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from hikeall.adapters.http import request_json
from hikeall.errors import WeatherUnavailable
from hikeall.models import Source
from hikeall.numfmt import Lang

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


_WEATHER_EN = {
    "clear": "Clear",
    "mostly_clear": "Mostly clear",
    "partly_cloudy": "Partly cloudy",
    "overcast": "Overcast",
    "fog": "Fog",
    "drizzle": "Drizzle",
    "freezing_drizzle": "Freezing drizzle",
    "light_rain": "Light rain",
    "rain": "Rain",
    "heavy_rain": "Heavy rain",
    "showers": "Rain showers",
    "freezing_rain": "Freezing rain",
    "snow": "Snow",
    "thunderstorm": "Thunderstorm",
}
_WEATHER_DE = {
    "clear": "Klar",
    "mostly_clear": "Überwiegend klar",
    "partly_cloudy": "Teils bewölkt",
    "overcast": "Bedeckt",
    "fog": "Nebel",
    "drizzle": "Nieselregen",
    "freezing_drizzle": "Gefrierender Nieselregen",
    "light_rain": "Regen",
    "rain": "Regen",
    "heavy_rain": "Regen",
    "showers": "Regenschauer",
    "freezing_rain": "Gefrierender Regen",
    "snow": "Schnee",
    "thunderstorm": "Gewitter",
}


def _weather_kind(code: int) -> str | None:
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return ("mostly_clear", "partly_cloudy", "overcast")[code - 1]
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 55:
        return "drizzle"
    if code in (56, 57):
        return "freezing_drizzle"
    if code in (61, 63, 65):
        return {61: "light_rain", 63: "rain", 65: "heavy_rain"}[code]
    if code in (80, 81, 82):
        return "showers"
    if code in (66, 67):
        return "freezing_rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 95 <= code <= 99:
        return "thunderstorm"
    return None


def weather_text(code: int | None, lang: Lang = "de") -> str | None:
    """WMO weather code (as sent by Open-Meteo) → short text in the reply language; None if
    unknown. German keeps one word for light/moderate/heavy rain, English tells them apart."""
    kind = _weather_kind(code) if code is not None else None
    if kind is None:
        return None
    return (_WEATHER_DE if lang == "de" else _WEATHER_EN)[kind]


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
        return self.daily_many([(lat, lon)], start, end)[0]

    def daily_many(
        self, points: list[tuple[float, float]], start: date, end: date
    ) -> list[list[DayWeather]]:
        """Daily weather for several locations in ONE request (Open-Meteo takes comma-separated
        coordinates and answers with a list, one entry per location, in the same order)."""
        if not points:
            return []
        data = request_json(
            self._http, "GET", FORECAST_URL, error_cls=WeatherUnavailable,
            params={
                "latitude": ",".join(f"{lat:.5f}" for lat, _ in points),
                "longitude": ",".join(f"{lon:.5f}" for _, lon in points),
                "daily": DAILY_FIELDS, "timezone": "Europe/Berlin",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
            },
            retries=2, backoff_s=self._backoff_s, rate_limit_wait_s=5.0,
        )
        entries = data if isinstance(data, list) else [data]
        if len(entries) != len(points):
            raise WeatherUnavailable("unexpected forecast format")
        return [_parse_daily(entry) for entry in entries]


def _parse_daily(data: object) -> list[DayWeather]:
    try:
        daily = data["daily"]  # type: ignore[index]
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
    except (TypeError, ValueError, AttributeError) as exc:
        raise WeatherUnavailable("unexpected forecast format") from exc
    return result
