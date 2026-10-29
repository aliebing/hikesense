import httpx
import pytest
import respx

from hikeall.adapters.http import USER_AGENT, make_http_client, request_json
from hikeall.errors import OverpassError

URL = "https://api.example.test/data"


@respx.mock
def test_retries_transient_then_succeeds():
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    with make_http_client(5) as client:
        assert request_json(client, "GET", URL, error_cls=OverpassError) == {"ok": True}
    assert route.call_count == 2
    assert route.calls[0].request.headers["User-Agent"] == USER_AGENT


@respx.mock
def test_timeout_raises_typed_error():
    respx.get(URL).mock(side_effect=httpx.ConnectTimeout("slow"))
    with make_http_client(5) as client, pytest.raises(OverpassError):
        request_json(client, "GET", URL, error_cls=OverpassError)


@respx.mock
def test_client_error_is_not_retried():
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with make_http_client(5) as client, pytest.raises(OverpassError, match="404"):
        request_json(client, "GET", URL, error_cls=OverpassError)
    assert route.call_count == 1


@respx.mock
def test_invalid_json_raises_typed_error():
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>"))
    with make_http_client(5) as client, pytest.raises(OverpassError, match="invalid JSON"):
        request_json(client, "GET", URL, error_cls=OverpassError)


@respx.mock
def test_429_honours_retry_after(monkeypatch):
    slept = []
    monkeypatch.setattr("hikeall.adapters.http.time.sleep", slept.append)
    respx.get(URL).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "3"}),
                                     httpx.Response(200, json={"ok": True})])
    with make_http_client(5) as client:
        assert request_json(client, "GET", URL, error_cls=OverpassError) == {"ok": True}
    assert slept == [3.0]


@respx.mock
def test_retry_after_is_capped(monkeypatch):
    slept = []
    monkeypatch.setattr("hikeall.adapters.http.time.sleep", slept.append)
    respx.get(URL).mock(side_effect=[httpx.Response(429, headers={"Retry-After": "600"}),
                                     httpx.Response(200, json={"ok": True})])
    with make_http_client(5) as client:
        request_json(client, "GET", URL, error_cls=OverpassError)
    assert slept == [30.0]


@respx.mock
def test_429_without_retry_after_waits_rate_limit_wait(monkeypatch):
    slept = []
    monkeypatch.setattr("hikeall.adapters.http.time.sleep", slept.append)
    respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, json={"ok": True})])
    with make_http_client(5) as client:
        request_json(client, "GET", URL, error_cls=OverpassError,
                     backoff_s=2.0, rate_limit_wait_s=60.0)
    assert slept == [60.0]
