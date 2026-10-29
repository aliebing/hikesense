from datetime import date

import pytest
from conftest import LINE

from hikeall.agent.request import Constraint, HikeRequest, ResolvedStart
from hikeall.agent.tools import (
    DbTools,
    find_accommodation,
    get_trail_details,
    hiking_time,
    search_day_hikes,
)
from hikeall.db import upsert_lodging, upsert_source, upsert_trail
from hikeall.models import BBox, Lodging, Source

SRC = Source(
    id="test-p2-src",
    name="t",
    url="https://example.org",
    license="ODbL",
    retrieved_at=date(2026, 10, 29),
)
# Test geometry sits at lat 40 (far from real Black Forest data); 1 degree lat ~ 111 km.
BASE_LAT = 40.0
START = ResolvedStart(kind="place", tag_id="start:x", label="X", lat=BASE_LAT, lon=8.0)


def shifted(dlat: float):
    return [(lat - 48.0 + BASE_LAT + dlat, lon) for lat, lon in LINE]


def add_trail(conn, id, dlat=0.0, kind="day_hike", length=7.4, ascent=100, descent=100):
    upsert_trail(
        conn,
        id=id,
        name=id,
        kind=kind,
        roundtrip=False,
        osm_relation_id=None,
        length_km=length,
        ascent_m=ascent,
        descent_m=descent,
        profile=[(0.0, 500.0), (7.4, 600.0)],
        line=shifted(dlat),
        source_id=SRC.id,
    )


@pytest.fixture
def db(conn):
    upsert_source(conn, SRC)
    return conn  # the conn fixture rolls back, so nothing test-p2-* persists


def req(radius=15.0, start=START):
    return HikeRequest(
        intent="day_hike", start=start, constraints=[Constraint(kind="radius_km", max=radius)]
    )


@pytest.mark.db
def test_search_returns_only_day_hikes_in_search_space(db):
    add_trail(db, "test-p2-near", 0.0)
    add_trail(db, "test-p2-long", 0.0, kind="long_distance")
    add_trail(db, "test-p2-far", 0.5)  # ~55 km, outside 45 km
    res = search_day_hikes(db, req())
    ids = {s.candidate.trail_id for s in res.selection.matches}
    assert "test-p2-near" in ids
    assert "test-p2-long" not in ids
    assert "test-p2-far" not in ids
    assert res.total_in_area == 1
    assert res.searched_radius_km == 45.0
    assert SRC.id in res.source_ids


@pytest.mark.db
def test_search_space_capped_at_50_km(db):
    assert search_day_hikes(db, req(radius=40.0)).searched_radius_km == 50.0


@pytest.mark.db
def test_area_start_uses_bbox(db):
    add_trail(db, "test-p2-in", 0.0)
    area = ResolvedStart(
        kind="area",
        tag_id="area:x",
        label="A",
        bbox=BBox(south=BASE_LAT - 0.01, west=7.99, north=BASE_LAT + 0.01, east=8.2),
    )
    res = search_day_hikes(db, HikeRequest(intent="day_hike", start=area))
    hit = [s for s in res.selection.matches if s.candidate.trail_id == "test-p2-in"]
    assert hit and hit[0].candidate.distance_km == 0


@pytest.mark.db
def test_radius_fallback_finds_trail_outside_radius(db):
    add_trail(db, "test-p2-18km", 18 / 111.2)
    res = search_day_hikes(db, req(radius=15.0))
    assert res.selection.matches == []
    fb = [s for s in res.selection.fallbacks if s.candidate.trail_id == "test-p2-18km"]
    assert fb
    assert fb[0].violated.kind == "radius_km"
    assert 17.5 < fb[0].candidate.distance_km < 18.5


@pytest.mark.db
def test_details_null_ascent_stays_null(db):
    add_trail(db, "test-p2-null")
    db.execute("update trails set ascent_m = null, descent_m = null where id = 'test-p2-null'")
    d = get_trail_details(db, "test-p2-null")
    assert d.ascent_m is None and d.descent_m is None
    assert d.length_km == 7.4
    assert d.pois == [] and d.stages == [] and d.photo_count == 0
    assert d.sources[0].id == SRC.id
    assert SRC.id in d.source_ids


@pytest.mark.db
def test_details_unknown_trail_is_none(db):
    assert get_trail_details(db, "test-p2-nope") is None


@pytest.mark.db
def test_accommodation_respects_max_dist(db):
    add_trail(db, "test-p2-lodg")
    for i, name in ((-9100001, "Nah"), (-9100002, "Fern")):
        upsert_lodging(db, Lodging(id=i, name=name, kind="hotel", lat=BASE_LAT, lon=8.0), SRC.id)
    db.execute(
        "insert into trail_lodgings (trail_id, lodging_id, dist_m, along_km) values "
        "('test-p2-lodg', -9100001, 300, 1.0), ('test-p2-lodg', -9100002, 2500, 2.0)"
    )
    assert [x.name for x in find_accommodation(db, "test-p2-lodg")] == ["Nah"]
    wide = find_accommodation(db, "test-p2-lodg", max_dist_m=3000)
    assert [x.name for x in wide] == ["Nah", "Fern"]
    ordered = find_accommodation(db, "test-p2-lodg", near_km=2.0, max_dist_m=3000)
    assert [x.name for x in ordered] == ["Fern", "Nah"]


def test_hiking_time_is_din33466():
    assert hiking_time(10, 600, 600).hours == 4.45


def test_search_knowledge_without_index_reports_missing():
    hits = DbTools(lambda: None).search_knowledge("Wasser")
    assert len(hits) == 1 and "Wissensindex fehlt" in hits[0].text
