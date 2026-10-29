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


@pytest.mark.parametrize(
    "remark",
    [
        "runtime error: Query timed out in \"query\" at line 1 after 26 seconds.",
        "runtime error: Query run out of memory using about 2048 MB of RAM.",
        "runtime remark: Timeout reached.",
    ],
)
@respx.mock
def test_200_with_remark_is_error_not_partial_data(remark):
    """Overpass reports timeouts/memory aborts as 200 + remark with truncated elements."""
    body = {"elements": [{"type": "node", "id": 1, "lat": 48.0, "lon": 8.0}], "remark": remark}
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=body))
    with make_http_client(5) as http, pytest.raises(OverpassError, match="remark|runtime"):
        OverpassClient(http, backoff_s=0).run("q")
