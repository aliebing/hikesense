import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from conftest import LINE

from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OVERPASS_URL, OverpassClient
from hikeall.db import upsert_source, upsert_trail
from hikeall.errors import OverpassError
from hikeall.ingest.places import (
    fetch_places,
    import_places,
    link_trail_pois,
    parse_places,
    parse_pois,
    places_query,
    pois_query,
)
from hikeall.models import BLACK_FOREST_BBOX, Place, Poi, Source

SRC = Source(
    id="test-osm-places",
    name="t",
    url="https://example.org",
    license="ODbL",
    retrieved_at=date(2026, 10, 29),
)
TRAIL = "test-pois-trail"


@pytest.fixture
def fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "overpass_places_small.json").read_text()
    )


def test_parse_pois_kinds(fixture):
    kinds = {p.kind for p in parse_pois(fixture)}
    assert kinds == {"viewpoint", "peak", "waterfall", "food", "hut", "station"}


def test_parse_pois_mapping_details(fixture):
    by_id = {p.id: p for p in parse_pois(fixture)}
    assert by_id[10].kind == "food" and by_id[10].name is None  # unnamed restaurant kept
    assert by_id[-12].kind == "hut"  # way id negative
    assert 13 in by_id and 14 not in by_id  # only basic_hut shelters
    assert 5 not in by_id  # unnamed peak dropped
    assert {15, 16} <= by_id.keys() and 17 not in by_id


def test_parse_places_requires_name(fixture):
    places = parse_places(fixture)
    assert places and all(p.name for p in places)
    assert {p.kind for p in places} == {"town", "village", "hamlet", "peak", "lake"}
    assert {p.id for p in places} == {1, 2, 3, 4, -6, -(10**12 + 18)}


def test_relation_lake_gets_distinct_id(fixture):
    lake = next(p for p in parse_places(fixture) if p.name == "Schluchsee")
    assert lake.kind == "lake" and lake.id == -(10**12 + 18)
    assert lake.id < -(10**11)  # cannot collide with negated way ids


def test_places_query_includes_relation_lakes():
    assert 'relation["natural"="water"]["water"="lake"]' in places_query(BLACK_FOREST_BBOX)


def test_queries_stay_in_bbox():
    for q in (places_query(BLACK_FOREST_BBOX), pois_query(BLACK_FOREST_BBOX)):
        assert "47.55,7.55,48.95,8.75" in q and "out center" in q


@respx.mock
def test_fetch_places_raises_on_overpass_remark():
    body = {"elements": [], "remark": 'runtime error: Query timed out in "query" at line 1.'}
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=body))
    with make_http_client(5) as http, pytest.raises(OverpassError):
        fetch_places(OverpassClient(http, backoff_s=0), BLACK_FOREST_BBOX, pause_s=0)


@pytest.fixture
def trail(conn):
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


def _links(conn):
    return conn.execute(
        "select poi_id, dist_m, along_km from trail_pois where trail_id = %s order by 1", [TRAIL]
    ).fetchall()


@pytest.mark.db
def test_link_trail_pois_respects_300m(conn, trail):
    # 0.0018 deg lat ~ 200 m, 0.0045 deg ~ 500 m north of the line
    pois = [
        Poi(id=9100001, kind="viewpoint", lat=48.0018, lon=8.05),
        Poi(id=9100002, kind="viewpoint", lat=48.0045, lon=8.05),
    ]
    import_places(conn, [], pois, SRC)
    rows = _links(conn)
    assert [r[0] for r in rows] == [9100001]
    assert 150 < rows[0][1] < 250 and abs(float(rows[0][2]) - 3.7) < 0.1
    # the far one is not kept; linking directly is stable too
    assert link_trail_pois(conn) >= 1


@pytest.mark.db
def test_import_places_is_idempotent(conn, trail):
    places = [Place(id=9100003, name="Testdorf", kind="village", lat=48.5, lon=8.5)]
    for _ in range(2):
        import_places(conn, places, [], SRC)
    n = conn.execute("select count(*) from places where id = 9100003").fetchone()[0]
    assert n == 1
