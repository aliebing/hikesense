import httpx
import pytest
import respx

from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OVERPASS_URL, OverpassClient
from hikeall.errors import OverpassError


@respx.mock
def test_run_posts_query_and_returns_elements():
    route = respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": []}))
    with make_http_client(5) as http:
        assert OverpassClient(http, backoff_s=0).run("[out:json];node(1);out;") == {"elements": []}
    assert b"data=" in route.calls[0].request.content


@respx.mock
def test_missing_elements_is_error():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json={"remark": "timeout"}))
    with make_http_client(5) as http, pytest.raises(OverpassError, match="elements"):
        OverpassClient(http, backoff_s=0).run("q")
