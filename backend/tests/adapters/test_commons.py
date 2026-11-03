import httpx
import pytest
import respx

from hikesense.adapters.commons import COMMONS_API, WIKIDATA_API, CommonsClient
from hikesense.adapters.http import make_http_client
from hikesense.errors import ImageFetchError


@respx.mock
def test_geosearch_returns_file_titles():
    respx.get(COMMONS_API).mock(return_value=httpx.Response(200, json={"query": {"geosearch": [
        {"title": "File:A.jpg"}, {"title": "File:B.png"}]}}))
    with make_http_client(5) as http:
        assert CommonsClient(http, backoff_s=0).geosearch(47.9, 8.1) == ["File:A.jpg", "File:B.png"]


@respx.mock
def test_image_infos_parse_thumb_author_license_and_strip_html():
    respx.get(COMMONS_API).mock(return_value=httpx.Response(200, json={"query": {"pages": [
        {"title": "File:Falls.jpg", "imageinfo": [{
            "thumburl": "https://upload.wikimedia.org/thumb/Falls.jpg/400px-Falls.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Falls.jpg",
            "extmetadata": {"Artist": {"value": '<a href="//x">Anna &amp; Ben</a>'},
                            "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
        {"title": "File:Map.svg", "imageinfo": [{"thumburl": "x", "descriptionurl": "y", "extmetadata": {}}]},
        {"title": "File:Gone.jpg", "missing": True},
    ]}}))
    with make_http_client(5) as http:
        infos = CommonsClient(http, backoff_s=0).image_infos(["File:Falls.jpg", "File:Map.svg", "File:Gone.jpg"])
    assert [(i.title, i.author, i.license) for i in infos] == [("File:Falls.jpg", "Anna & Ben", "CC BY-SA 4.0")]
    assert infos[0].thumb_url.endswith("400px-Falls.jpg")
    assert infos[0].page_url == "https://commons.wikimedia.org/wiki/File:Falls.jpg"


@respx.mock
def test_wikidata_image():
    respx.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json={"claims": {"P18": [
        {"mainsnak": {"datavalue": {"value": "Titisee 01.jpg"}}}]}}))
    with make_http_client(5) as http:
        assert CommonsClient(http, backoff_s=0).wikidata_image("Q316401") == "File:Titisee 01.jpg"


@respx.mock
def test_errors_are_typed():
    respx.get(COMMONS_API).mock(return_value=httpx.Response(500))
    with make_http_client(5) as http, pytest.raises(ImageFetchError):
        CommonsClient(http, backoff_s=0).geosearch(47.9, 8.1)
