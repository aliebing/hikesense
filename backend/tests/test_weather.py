import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from hikeall.adapters.http import make_http_client
from hikeall.adapters.open_meteo import FORECAST_URL, DayWeather, OpenMeteoClient
from hikeall.agent import weather
from hikeall.agent.weather import NoForecast, is_rain_day, weather_for

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "open_meteo_daily.json").read_text())
TODAY = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def _clear_cache():
    weather._cache.clear()


@pytest.fixture
def client():
    with make_http_client(5) as http:
        yield OpenMeteoClient(http, backoff_s=0)


@respx.mock
def test_day_15_has_no_forecast(client):
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    far = date(2026, 11, 14)  # today + 15
    assert weather_for(client, 47.9, 8.1, far, TODAY) == NoForecast("Noch keine Vorhersage (mehr als 14 Tage)")
    assert weather_for(client, 47.9, 8.1, date(2026, 10, 29), TODAY) == NoForecast(
        "Datum liegt in der Vergangenheit")
    assert not route.called


@respx.mock
def test_missing_values_stay_none(client):
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    w = weather_for(client, 47.9, 8.1, date(2026, 11, 1), TODAY)
    assert w == DayWeather(date=date(2026, 11, 1))
    assert is_rain_day(w) is None
    full = client.daily(47.9, 8.1, TODAY, date(2026, 10, 31))
    assert (full[0].code, full[0].text, full[0].t_min_c, full[0].t_max_c) == (3, "Bedeckt", 4.1, 11.4)
    assert full[1].text == "Regen" and full[1].precip_mm == 7.5 and full[1].precip_prob_pct == 85


def test_rain_day_threshold():
    d = date(2026, 10, 30)
    assert is_rain_day(DayWeather(d, precip_prob_pct=59, precip_mm=4.9)) is False
    assert is_rain_day(DayWeather(d, precip_prob_pct=60)) is True
    assert is_rain_day(DayWeather(d, precip_mm=5.0)) is True


@respx.mock
def test_network_error_is_no_forecast(client):
    respx.get(FORECAST_URL).mock(side_effect=httpx.ConnectError("down"))
    assert weather_for(client, 47.9, 8.1, TODAY, TODAY) == NoForecast("Wetterdienst nicht erreichbar")


@respx.mock
def test_cache_hits_once(client):
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    a = weather_for(client, 47.901, 8.102, TODAY, TODAY)
    b = weather_for(client, 47.899, 8.098, TODAY, TODAY)  # same cell at 2 decimals
    assert a == b and a.text == "Bedeckt"
    assert route.call_count == 1


@respx.mock
def test_day_14_ahead_still_has_forecast(client):
    last = date(2026, 11, 13)  # today + 14
    body = {"daily": {"time": [last.isoformat()], "weather_code": [2], "temperature_2m_max": [9.0],
                      "temperature_2m_min": [2.0], "precipitation_sum": [0.0],
                      "precipitation_probability_max": [5]}}
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=body))
    w = weather_for(client, 47.9, 8.1, last, TODAY)
    assert isinstance(w, DayWeather) and w.text == "Teils bewölkt"
    assert route.call_count == 1


@respx.mock
def test_expired_cache_refetches(client, monkeypatch):
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    now = [1000.0]
    monkeypatch.setattr(weather.time, "monotonic", lambda: now[0])
    weather_for(client, 47.9, 8.1, TODAY, TODAY)
    now[0] += 3599
    weather_for(client, 47.9, 8.1, TODAY, TODAY)
    assert route.call_count == 1
    now[0] += 2
    weather_for(client, 47.9, 8.1, TODAY, TODAY)
    assert route.call_count == 2


def _entry(days, prob):
    return {
        "daily": {
            "time": [d.isoformat() for d in days],
            "weather_code": [61] * len(days),
            "temperature_2m_min": [-3.0] * len(days),
            "temperature_2m_max": [4.0] * len(days),
            "precipitation_sum": [1.0] * len(days),
            "precipitation_probability_max": [prob] * len(days),
        }
    }


@respx.mock
def test_many_days_and_places_in_one_request_then_cached(client):
    from datetime import timedelta

    from hikeall.agent.weather import weather_for_days

    days = [TODAY + timedelta(days=n) for n in range(15)]  # 0..14: all in the horizon
    points = [(47.9 + n / 10, 8.1, d) for n, d in enumerate(days)]
    body = [_entry(days, n) for n in range(15)]  # one list entry per location
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=body))
    got = weather_for_days(client, points, TODAY)
    assert route.call_count == 1
    params = route.calls[0].request.url.params
    assert len(params["latitude"].split(",")) == 15
    assert (params["start_date"], params["end_date"]) == ("2026-10-30", "2026-11-13")
    assert [w.precip_prob_pct for w in got] == list(range(15))
    assert weather_for_days(client, points, TODAY) == got  # 1 h cache: no second request
    assert route.call_count == 1
    far = weather_for_days(client, [(47.9, 8.1, TODAY + timedelta(days=15))], TODAY)
    assert far == [NoForecast("Noch keine Vorhersage (mehr als 14 Tage)")]
    assert route.call_count == 1


@respx.mock
def test_many_days_failure_is_no_forecast_for_each(client):
    from hikeall.agent.weather import weather_for_days

    respx.get(FORECAST_URL).mock(side_effect=httpx.ConnectError("down"))
    got = weather_for_days(client, [(47.9, 8.1, TODAY), (48.0, 8.2, TODAY)], TODAY)
    assert got == [NoForecast("Wetterdienst nicht erreichbar")] * 2
