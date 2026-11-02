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


# --- English texts and reason codes (Zweisprachig Teil B, Task 5) -----------------------------


def test_weather_text_english():
    from hikeall.adapters.open_meteo import weather_text

    assert weather_text(61, "en") == "Light rain"
    assert weather_text(63, "en") == "Rain" and weather_text(65, "en") == "Heavy rain"
    assert weather_text(80, "en") == "Rain showers" and weather_text(95, "en") == "Thunderstorm"
    assert weather_text(2, "en") == "Partly cloudy" and weather_text(None, "en") is None
    assert weather_text(999, "en") is None
    # German is unchanged: one word for light, moderate and heavy rain
    assert [weather_text(c) for c in (61, 63, 65, 80)] == ["Regen", "Regen", "Regen", "Regenschauer"]


@respx.mock
def test_reason_codes(client):
    respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    far = weather_for(client, 47.9, 8.1, date(2026, 11, 14), TODAY)
    past = weather_for(client, 47.9, 8.1, date(2026, 10, 29), TODAY)
    assert (far.code, past.code) == ("not_yet", "past")
    respx.get(FORECAST_URL).mock(side_effect=httpx.ConnectError("down"))
    assert weather_for(client, 47.9, 8.1, TODAY, TODAY).code == "unavailable"


def test_localize_forecast_and_reasons():
    from hikeall.agent.weather import localize, no_forecast

    d = date(2026, 11, 3)
    w = DayWeather(d, code=61, text="Regen")
    assert localize(w, "en").text == "Light rain" and localize(w, "de") is w
    assert w.text == "Regen"  # the cached object is not touched
    nf = no_forecast("not_yet")
    assert nf.reason == "Noch keine Vorhersage (mehr als 14 Tage)"
    assert localize(nf, "en").reason == "No forecast yet (more than 14 days ahead)"
    assert localize(nf, "en").code == "not_yet"
    assert no_forecast("no_place", "en").reason == "Place for the forecast unknown"


# --- weather wishes (Stufe 4) ---

D = date(2026, 10, 30)


def _w(code=1, mm=0.0, prob=0, snow=0.0):
    return DayWeather(D, code=code, precip_mm=mm, precip_prob_pct=prob, snowfall_cm=snow)


def test_fine_thresholds():
    assert weather.matches(_w(mm=0.5, prob=30), "fine") is True
    assert weather.matches(_w(mm=0.6), "fine") is False
    assert weather.matches(_w(prob=31), "fine") is False
    assert weather.matches(_w(code=3), "fine") is True
    assert weather.matches(_w(code=45), "fine") is False


def test_dry_thresholds():
    assert weather.matches(_w(code=61, mm=1.0, prob=40), "dry") is True
    assert weather.matches(_w(mm=1.1), "dry") is False
    assert weather.matches(_w(prob=41), "dry") is False


def test_snow_thresholds():
    assert weather.matches(_w(snow=1.0), "snow") is True
    assert weather.matches(_w(snow=0.9), "snow") is False
    assert weather.matches(_w(code=73, snow=0.0), "snow") is True
    assert weather.matches(_w(code=61, snow=0.0), "snow") is False


def test_matches_missing_values_are_none():
    assert weather.matches(DayWeather(D), "fine") is None
    assert weather.matches(DayWeather(D, code=1, precip_mm=0.0), "fine") is None
    assert weather.matches(DayWeather(D, precip_mm=0.0), "dry") is None
    assert weather.matches(DayWeather(D, code=1), "snow") is None
    assert weather.matches(DayWeather(D, snowfall_cm=2.0), "snow") is True


def test_score_order():
    assert weather.score(_w(mm=0.0, prob=10), "fine") > weather.score(_w(mm=0.0, prob=20), "fine")
    assert weather.score(_w(mm=0.2, prob=0), "dry") > weather.score(_w(mm=0.8, prob=0), "dry")
    assert weather.score(_w(snow=5.0), "snow") > weather.score(_w(snow=1.0), "snow")
    assert weather.score(DayWeather(D), "dry") < weather.score(_w(mm=5.0, prob=90), "dry")


class FakeRangeClient:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def daily_many(self, points, start, end):
        from datetime import timedelta

        from hikeall.errors import WeatherUnavailable

        self.calls.append((list(points), start, end))
        if self.fail:
            raise WeatherUnavailable("down")
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        return [[DayWeather(date=d, code=1, precip_mm=0.0) for d in days] for _ in points]


def test_forecast_range_one_request_15_days_and_cache():
    fake = FakeRangeClient()
    pts = [(47.9, 8.1), (48.2, 8.4)]
    got = weather.forecast_range(fake, pts, TODAY)
    assert len(fake.calls) == 1 and fake.calls[0][1:] == (TODAY, date(2026, 11, 13))
    assert [len(x) for x in got] == [15, 15]
    assert weather.forecast_range(fake, pts, TODAY) == got
    assert len(fake.calls) == 1
    weather.forecast_range(fake, [(47.9, 8.1), (50.0, 9.0)], TODAY)  # only the new point
    assert len(fake.calls) == 2 and fake.calls[1][0] == [(50.0, 9.0)]


def test_forecast_range_failure_is_no_forecast_and_not_cached():
    got = weather.forecast_range(FakeRangeClient(fail=True), [(47.9, 8.1)], TODAY)
    assert got == NoForecast("Wetterdienst nicht erreichbar") and got.code == "unavailable"
    ok = FakeRangeClient()
    assert isinstance(weather.forecast_range(ok, [(47.9, 8.1)], TODAY), list)
    assert len(ok.calls) == 1


@respx.mock
def test_parser_reads_snowfall(client):
    data = json.loads(json.dumps(FIXTURE))
    data["daily"]["snowfall_sum"] = [0.0, 2.4, None]
    route = respx.get(FORECAST_URL).mock(return_value=httpx.Response(200, json=data))
    days = client.daily(47.9, 8.1, TODAY, date(2026, 11, 1))
    assert [d.snowfall_cm for d in days] == [0.0, 2.4, None]
    assert "snowfall_sum" in str(route.calls[0].request.url)
