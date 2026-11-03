from datetime import date, time

import pytest
from conftest import L_CORNER_KM, LINE, upsert_l_trail

from hikesense.agent.multiday import DayPlan, start_km_for
from hikesense.agent.request import Constraint, HikeRequest, ResolvedStart
from hikesense.agent.tools import (
    TOOL_SPECS,
    DbTools,
    KnowledgeHit,
    day_end_points,
    find_accommodation,
    get_trail_details,
    hiking_time,
    search_day_hikes,
)
from hikesense.db import upsert_lodging, upsert_photo, upsert_source, upsert_trail
from hikesense.models import BBox, Lodging, Source

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
        kind=kind, region="black_forest",
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


def add_poi(db, id, kind="viewpoint", source="test-p2-src"):
    db.execute(
        "insert into pois (id, name, kind, geom, source_id) "
        "values (%s, %s, %s, st_setsrid(st_makepoint(8.0, 40.0), 4326), %s)",
        (id, f"poi{id}", kind, source),
    )


@pytest.mark.db
def test_details_pois_limited_ordered_and_sources_complete(db):
    add_trail(db, "test-p2-poi")
    upsert_source(
        db,
        Source(id="test-p2-src2", name="p", url="u", license="l", retrieved_at=date(2026, 10, 29)),
    )
    for i in range(12):
        add_poi(db, -9200000 - i, source="test-p2-src2" if i == 11 else "test-p2-src")
        db.execute(
            "insert into trail_pois (trail_id, poi_id, dist_m, along_km) values (%s, %s, 10, %s)",
            ("test-p2-poi", -9200000 - i, 12 - i),  # higher i = smaller along_km
        )
    d = get_trail_details(db, "test-p2-poi")
    assert len(d.pois) == 10
    assert [p.along_km for p in d.pois] == sorted(p.along_km for p in d.pois)
    assert d.pois[0].along_km == 1  # i=11 (source 2) is first
    assert d.source_ids == ["test-p2-src", "test-p2-src2"]
    assert [s.id for s in d.sources] == d.source_ids


@pytest.mark.db
def test_details_include_stages(db):
    add_trail(db, "test-p2-stg")
    db.execute(
        "insert into stages (id, trail_id, seq, name, length_km, source_id) values "
        "('test-p2-stg-2', 'test-p2-stg', 2, 'B', 5, 'test-p2-src'), "
        "('test-p2-stg-1', 'test-p2-stg', 1, 'A', 3, 'test-p2-src')"
    )
    d = get_trail_details(db, "test-p2-stg")
    assert [(s.seq, s.name, s.length_km, s.ascent_m) for s in d.stages] == [
        (1, "A", 3.0, None),
        (2, "B", 5.0, None),
    ]


@pytest.mark.db
def test_accommodation_limited_to_10(db):
    add_trail(db, "test-p2-many")
    for i in range(12):
        upsert_lodging(
            db, Lodging(id=-9300000 - i, name=f"L{i}", kind="hotel", lat=BASE_LAT, lon=8.0), SRC.id
        )
        db.execute(
            "insert into trail_lodgings values ('test-p2-many', %s, 100, %s)", (-9300000 - i, i)
        )
    assert len(find_accommodation(db, "test-p2-many")) == 10


@pytest.mark.parametrize("bad", [0, -1, 5001])
def test_accommodation_rejects_bad_max_dist(bad):
    with pytest.raises(ValueError):
        find_accommodation(None, "x", max_dist_m=bad)


@pytest.mark.db
def test_candidate_tags_come_from_trail_tags(db):
    add_trail(db, "test-p2-tag")
    db.execute(
        "insert into trail_tags values ('test-p2-tag', 'surface:paved'), ('test-p2-tag', 'view')"
    )
    res = search_day_hikes(db, req())
    m = [s for s in res.selection.matches if s.candidate.trail_id == "test-p2-tag"]
    assert m[0].candidate.tags == {"surface:paved", "view"}


def test_tool_specs_exactly_four_without_day_hike_search():
    names = [s["function"]["name"] for s in TOOL_SPECS]
    assert names == ["get_trail_details", "find_accommodation", "hiking_time", "search_knowledge"]
    spec = next(s for s in TOOL_SPECS if s["function"]["name"] == "find_accommodation")
    assert (
        "sortiert nach Nähe"
        in spec["function"]["parameters"]["properties"]["near_km"]["description"]
    )


class CountingFactory:
    """Hands out a wrapper around the test connection and records close-on-exit."""

    def __init__(self, conn):
        self.conn, self.opened, self.closed = conn, 0, 0

    def __call__(self):
        self.opened += 1
        return self

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        self.closed += 1


@pytest.mark.db
def test_dbtools_delegates_and_closes_each_call(db):
    add_trail(db, "test-p2-del")
    f = CountingFactory(db)
    tools = DbTools(f)
    assert tools.search_day_hikes(req()).total_in_area == 1
    assert tools.get_trail_details("test-p2-del").name == "test-p2-del"
    assert tools.find_accommodation("test-p2-del") == []
    assert tools.hiking_time(10, 600, 600).hours == 4.45
    assert f.opened == f.closed == 3  # hiking_time needs no connection


def test_dbtools_knowledge_delegates():
    class Idx:
        def search(self, q, k=5):
            return [KnowledgeHit(text=f"{q}{k}")]

    assert DbTools(lambda: None, Idx()).search_knowledge("a", 2)[0].text == "a2"


def _photo(conn, trail_id, n):
    upsert_photo(
        conn,
        trail_id=trail_id,
        stage_id=None,
        url=f"https://commons.example/test-p2-{trail_id}-{n}.jpg",
        thumb_url=f"https://commons.example/thumb/test-p2-{trail_id}-{n}.jpg",
        author="A",
        license="CC BY-SA 4.0",
        license_url="https://license.example/by-sa",
        page_url=f"https://commons.example/page/{n}",
    )


@pytest.mark.db
def test_search_cards_get_first_commons_thumb(db):
    add_trail(db, "test-p2-photo")
    add_trail(db, "test-p2-nophoto", dlat=0.01)
    _photo(db, "test-p2-photo", 1)
    _photo(db, "test-p2-photo", 2)
    res = search_day_hikes(db, req())
    by_id = {s.candidate.trail_id: s.candidate for s in res.selection.matches}
    assert by_id["test-p2-photo"].cover_thumb_url == (
        "https://commons.example/thumb/test-p2-test-p2-photo-1.jpg"
    )
    assert by_id["test-p2-photo"].cover_url == "https://commons.example/test-p2-test-p2-photo-1.jpg"
    assert by_id["test-p2-nophoto"].cover_thumb_url is None
    assert by_id["test-p2-nophoto"].cover_url is None
    c = by_id["test-p2-photo"]
    assert (c.cover_author, c.cover_license) == ("A", "CC BY-SA 4.0")
    assert c.cover_license_url == "https://license.example/by-sa"
    assert c.cover_page_url == "https://commons.example/page/1"
    n = by_id["test-p2-nophoto"]
    assert (n.cover_author, n.cover_license, n.cover_license_url, n.cover_page_url) == (None,) * 4


# --- final fix wave ---------------------------------------------------------------------------


@pytest.mark.db
def test_search_returns_full_source_briefs(db):
    add_trail(db, "test-p2-src-brief")
    result = search_day_hikes(db, req())
    assert [(s.id, s.name, s.url, s.license) for s in result.sources] == [
        (SRC.id, SRC.name, SRC.url, SRC.license)
    ]


def test_dbtools_reopens_a_missing_knowledge_index_lazily():
    class Idx:
        def search(self, q, k=5):
            return [KnowledgeHit(text="gefunden")]

    built: list = [None]
    tools = DbTools(lambda: None, None, knowledge_opener=lambda: built[0])
    assert "Wissensindex fehlt" in tools.search_knowledge("a")[0].text
    built[0] = Idx()  # `make knowledge` ran while the API was up
    assert tools.search_knowledge("a")[0].text == "gefunden"


# --- multi-day tools (plan 3, task 7) ------------------------------------------------------


class _FixedWeather:
    """OpenMeteoClient stand-in: dry days, no network; counts the requests."""

    requests = 0

    def daily_many(self, points, start, end):
        from datetime import timedelta

        from hikesense.adapters.open_meteo import DayWeather

        self.requests += 1
        days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        return [[DayWeather(date=d, text="Klar", precip_mm=0.0) for d in days] for _ in points]


def test_dbtools_weather_without_client_is_no_forecast():
    from hikesense.agent.weather import REASON_DOWN, NoForecast

    got = DbTools(lambda: None).weather_days([(48.0, 8.0, date.today())], date.today())
    assert got == [NoForecast(REASON_DOWN)]


@pytest.mark.db
def test_dbtools_multiday_on_the_real_westweg(db):
    from hikesense.agent import weather as weather_module
    from hikesense.agent.request import DayChange
    from hikesense.agent.tools import StartNotOnTrail

    weather_module._cache.clear()
    client = _FixedWeather()
    tools = DbTools(CountingFactory(db), weather_client=client)
    hausach = ResolvedStart(
        kind="place", tag_id="place:hausach", label="Hausach", lat=48.2836305, lon=8.174972
    )
    request = HikeRequest(
        intent="multiday", start=hausach, trail_id="westweg-west", days=14,
        start_date=date.today(),
    )  # fmt: skip
    plan = tools.plan_multiday(request)
    assert len(plan.days) >= 5 and plan.trail_name == "Westweg (Westvariante)"
    assert {"osm", "stages-schwarzwald-tourismus"} <= set(plan.source_ids)
    points = tools.day_end_points(plan.trail_id, plan.days)  # one query for all days
    assert set(points) == {d.day for d in plan.days}
    for lat, lon in points.values():
        assert 47.5 < lat < 49.0 and 7.5 < lon < 8.8  # in the Black Forest
    wanted = [(*points[d.day], d.date) for d in plan.days]
    got = tools.weather_days(wanted, date.today())
    assert client.requests == 1 and all(w.text == "Klar" for w in got[:15])
    rain = tools.rain_variants(plan, [1, 2])
    assert set(rain) == {1, 2}
    changed = tools.change_day(plan, DayChange(day=2, change="shorter"), start_name="Hausach")
    assert changed.days[0] == plan.days[0]
    names = {s.id: s.name for s in tools.sources(plan.source_ids)}
    assert names["osm"] and names["stages-schwarzwald-tourismus"]
    basel = hausach.model_copy(update={"label": "Basel", "lat": 47.5673009, "lon": 7.6069164})
    with pytest.raises(StartNotOnTrail):  # the trail end: nothing left to plan
        tools.plan_multiday(request.model_copy(update={"start": basel}))


@pytest.mark.db
def test_km_positions_on_the_trail_count_metres_not_degrees(conn):
    """start_km and the point at a day's end_km are inverse and measured in metres: the corner
    of the L lies at 5,56 km (as a degree fraction it would be 4,46 km)."""
    upsert_source(conn, SRC)
    upsert_l_trail(conn, "test-l-trail", SRC.id)
    km = start_km_for(conn, "test-l-trail", 48.05, 8.0)
    assert km is not None and abs(km - L_CORNER_KM) < 0.05
    day = DayPlan(
        day=1, date=None, start_km=0.0, end_km=L_CORNER_KM, walk_km=L_CORNER_KM, access_km=0.0,
        length_km=L_CORNER_KM, ascent_m=0, descent_m=0, duration_h=1.5, start_time=time(9),
        arrival=time(10, 30), stop=None, gap=None, within_band=True,
    )  # fmt: skip
    lat, lon = day_end_points(conn, "test-l-trail", [day])[1]
    assert abs(lat - 48.05) < 0.0005 and abs(lon - 8.0) < 0.0007  # within ~50 m of the corner
