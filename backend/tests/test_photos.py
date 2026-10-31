import httpx
import pytest
import respx
from conftest import LINE

from hikeall.adapters.commons import COMMONS_API, CommonsClient, ImageInfo
from hikeall.adapters.http import make_http_client
from hikeall.db import upsert_source, upsert_trail
from hikeall.errors import ImageFetchError
from hikeall.ingest.photos import (
    Target,
    fetch_photos,
    import_photos,
    sample_points,
    select_photos,
)
from hikeall.models import Source

SRC = Source(id="osm-t8", name="t", url="u", license="l", retrieved_at="2026-10-28")


def info(url, author="X", license="CC BY-SA 4.0", w=1600, h=900, title=None):
    return ImageInfo(
        title=title or f"File:{url}.jpg",
        thumb_url=f"t-{url}",
        page_url=f"https://commons.wikimedia.org/wiki/File:{url}.jpg",
        author=author,
        license=license,
        url=url,
        width=w,
        height=h,
    )


def test_sample_points_every_km():
    pts = sample_points(LINE, every_km=2)  # LINE ~7.4 km
    assert len(pts) == 4 and pts[0] == LINE[0]
    assert sample_points([LINE[0]], every_km=2) == [LINE[0]]
    assert sample_points([], every_km=2) == []


def test_select_photos_drops_missing_license_and_portrait():
    infos = [
        info("a"),
        info("b", author=""),
        info("c", license=None),
        info("d", license="CC0", w=900, h=1600),
        info("e", w=1000, h=900),  # 1.11:1, narrower than 1.2:1
        info("a"),
    ]
    assert [p.url for p in select_photos(infos, limit=8)] == ["a"]


def test_select_photos_limit_exclude_and_title_filter():
    infos = [info(str(i)) for i in range(6)] + [info("sign", title="File:Wegweiser Kandel.jpg")]
    assert [p.url for p in select_photos(infos, limit=3)] == ["0", "1", "2"]
    assert [p.url for p in select_photos(infos, limit=8, exclude={"1"})] == [
        "0",
        "2",
        "3",
        "4",
        "5",
    ]


def test_select_photos_prefers_landscape_titles():
    infos = [info("a", title="File:Foo.jpg"), info("b", title="File:Blick vom Feldberg.jpg")]
    assert [p.url for p in select_photos(infos, limit=1)] == ["b"]


def _page(title, n):
    return {
        "title": title,
        "imageinfo": [
            {
                "thumburl": f"https://upload.wikimedia.org/{n}",
                "url": f"https://upload.wikimedia.org/orig/{n}",
                "width": 4000,
                "height": 2000,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
                "extmetadata": {
                    "Artist": {"value": "A"},
                    "LicenseShortName": {"value": "CC BY 4.0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
                },
            }
        ],
    }


def _router(request):
    p = request.url.params
    if p.get("list") == "geosearch":
        # every sample point sees the same two files: duplicates across points
        return httpx.Response(
            200, json={"query": {"geosearch": [{"title": "File:A.jpg"}, {"title": "File:B.jpg"}]}}
        )
    w = p["iiurlwidth"]
    return httpx.Response(
        200,
        json={"query": {"pages": [_page("File:A.jpg", f"{w}/A"), _page("File:B.jpg", f"{w}/B")]}},
    )


@respx.mock
def test_fetch_photos_dedupes_across_points_and_sets_sizes():
    route = respx.get(COMMONS_API).mock(side_effect=_router)
    with make_http_client(5) as http:
        client = CommonsClient(http, backoff_s=0)
        photos = fetch_photos(client, LINE, every_km=2, limit=8, pause_s=0)
    assert [p.url.rsplit("/", 1)[-1] for p in photos] == ["A", "B"]
    assert photos[0].thumb_url.endswith("400/A") and "1600/A" in photos[0].url
    assert photos[0].license_url == "https://creativecommons.org/licenses/by/4.0/"
    assert route.call_count == 4 + 2  # 4 geosearches, then 400 px and 1600 px imageinfo batches


@respx.mock
def test_fetch_photos_respects_limit():
    respx.get(COMMONS_API).mock(side_effect=_router)
    with make_http_client(5) as http:
        photos = fetch_photos(
            CommonsClient(http, backoff_s=0), LINE, every_km=2, limit=1, pause_s=0
        )
    assert len(photos) == 1


@respx.mock
def test_api_failure_raises_after_retries():
    route = respx.get(COMMONS_API).mock(return_value=httpx.Response(503))
    with make_http_client(5) as http, pytest.raises(ImageFetchError):
        fetch_photos(CommonsClient(http, backoff_s=0), LINE, every_km=2, limit=8, pause_s=0)
    assert route.call_count == 3  # first attempt + 2 retries


TRAIL = "t8-day"


def _trail(conn):
    upsert_source(conn, SRC)
    upsert_trail(
        conn,
        id=TRAIL,
        name="T",
        kind="day_hike",
        roundtrip=False,
        osm_relation_id=None,
        length_km=7.4,
        ascent_m=0,
        descent_m=0,
        profile=[(0.0, 500.0)],
        line=LINE,
        source_id=SRC.id,
    )


def _count(conn):
    return conn.execute("select count(*) from photos where trail_id = %s", [TRAIL]).fetchone()[0]


@pytest.mark.db
@respx.mock
def test_import_is_idempotent_and_stores_attribution(conn):
    _trail(conn)
    respx.get(COMMONS_API).mock(side_effect=_router)
    target = Target(trail_id=TRAIL, stage_id=None, line=LINE, every_km=2, limit=5)
    with make_http_client(5) as http:
        client = CommonsClient(http, backoff_s=0)
        for _ in range(2):
            rep = import_photos(conn, client, [target], pause_s=0)
            assert rep.counts[TRAIL] == 2
            assert _count(conn) == 2
    row = conn.execute(
        "select source, author, license, license_url, page_url, thumb_url, stage_id from photos"
        " where trail_id = %s order by id limit 1",
        [TRAIL],
    ).fetchone()
    assert row[0] == "commons" and row[1] == "A" and row[2] == "CC BY 4.0"
    assert row[3].startswith("https://creativecommons.org") and row[4].startswith("https://commons")
    assert row[6] is None
    assert conn.execute("select 1 from sources where id = 'commons'").fetchone()


@pytest.mark.db
@respx.mock
def test_api_failure_writes_nothing(conn):
    _trail(conn)
    respx.get(COMMONS_API).mock(return_value=httpx.Response(500))
    target = Target(trail_id=TRAIL, stage_id=None, line=LINE, every_km=2, limit=5)
    with make_http_client(5) as http, pytest.raises(ImageFetchError):
        import_photos(conn, CommonsClient(http, backoff_s=0), [target], pause_s=0)
    assert _count(conn) == 0


@respx.mock
def test_api_error_in_200_body_is_retried_then_raises():
    busy = {"error": {"code": "cirrussearch-too-busy-error", "info": "busy"}}
    route = respx.get(COMMONS_API).mock(return_value=httpx.Response(200, json=busy))
    with make_http_client(5) as http, pytest.raises(ImageFetchError, match="too-busy"):
        fetch_photos(CommonsClient(http, backoff_s=0), LINE, every_km=2, limit=8, pause_s=0)
    assert route.call_count == 3


@pytest.mark.db
@respx.mock
def test_rerun_of_one_stage_keeps_other_stages_photos(conn):
    from hikeall.db import upsert_stage

    _trail(conn)
    for seq in (1, 2):
        upsert_stage(
            conn,
            id=f"{TRAIL}-{seq}",
            trail_id=TRAIL,
            seq=seq,
            name="S",
            start_name="a",
            end_name="b",
            length_km=7.4,
            ascent_m=0,
            descent_m=0,
            profile=[(0.0, 500.0)],
            line=LINE,
            source_id=SRC.id,
        )
    respx.get(COMMONS_API).mock(side_effect=_router)
    t1 = Target(trail_id=TRAIL, stage_id=f"{TRAIL}-1", line=LINE, every_km=2, limit=1)
    t2 = Target(trail_id=TRAIL, stage_id=f"{TRAIL}-2", line=LINE, every_km=2, limit=1)
    with make_http_client(5) as http:
        client = CommonsClient(http, backoff_s=0)
        import_photos(conn, client, [t1, t2], pause_s=0)
        assert _count(conn) == 2  # stage 2 gets B: A is taken by stage 1
        import_photos(conn, client, [t1], pause_s=0)
    assert _count(conn) == 2


def test_photo_summary_counts_every_long_distance_trail():
    from hikeall.cli import photo_summary

    counts = {"westweg-west": 5, "mittelweg": 3, "feldberg": 2}
    lines = photo_summary(counts, long_distance={"westweg-west", "mittelweg"})
    assert lines[:2] == ["mittelweg: 3 Bilder", "westweg-west: 5 Bilder"]
    assert lines[2] == "10 Bilder, 2 Fernwege, 1 Tagestouren (2 Bilder an Tagestouren)"
