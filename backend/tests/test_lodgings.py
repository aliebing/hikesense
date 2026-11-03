from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from conftest import L_CORNER_KM, LINE, upsert_l_trail

from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OVERPASS_URL, OverpassClient
from hikeall.db import upsert_lodging, upsert_source, upsert_trail
from hikeall.errors import OverpassError
from hikeall.ingest.lodgings import (
    fetch_lodgings,
    import_lodgings,
    link_trail_lodgings,
    lodgings_query,
    parse_lodgings,
)
from hikeall.models import BLACK_FOREST_BBOX, Lodging, Source

SRC = Source(
    id="test-osm-lodg",
    name="t",
    url="https://example.org",
    license="ODbL",
    retrieved_at=date(2026, 10, 28),
)
TRAIL = "test-lodg-trail"


def el(id, tags, type="node"):
    e = {"type": type, "id": id, "tags": tags}
    e.update({"center": {"lat": 48, "lon": 8}} if type == "way" else {"lat": 48, "lon": 8})
    return e


def test_parse_lodgings_keeps_named_relevant_kinds():
    data = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 48,
                "lon": 8,
                "tags": {"tourism": "guest_house", "name": "Pension A"},
            },
            {
                "type": "way",
                "id": 2,
                "center": {"lat": 48, "lon": 8},
                "tags": {"tourism": "hotel", "name": "Hotel B", "contact:website": "https://b.de"},
            },
            {
                "type": "node",
                "id": 3,
                "lat": 48,
                "lon": 8,
                "tags": {"tourism": "museum", "name": "Museum"},
            },
            {"type": "node", "id": 4, "lat": 48, "lon": 8, "tags": {"tourism": "hotel"}},
        ]
    }
    ls = parse_lodgings(data)
    assert [(l.id, l.website) for l in ls] == [(1, None), (-2, "https://b.de")]


def test_parse_drops_blank_name_prefers_website_and_all_kinds():
    kinds = [
        "hotel",
        "guest_house",
        "hostel",
        "alpine_hut",
        "wilderness_hut",
        "chalet",
        "apartment",
        "camp_site",
    ]
    els = [el(i, {"tourism": k, "name": f"N{i}"}) for i, k in enumerate(kinds, 10)]
    els.append(el(50, {"tourism": "hotel", "name": "  "}))
    els.append(
        el(
            51,
            {
                "tourism": "hotel",
                "name": "W",
                "website": "https://a",
                "contact:website": "https://c",
            },
        )
    )
    els.append(el(52, {"tourism": "hotel", "name": "X", "contact:website": "https://c"}, "way"))
    els.append({"type": "way", "id": 53, "tags": {"tourism": "hotel", "name": "no center"}})
    ls = parse_lodgings({"elements": els})
    assert [l.kind for l in ls[:8]] == kinds
    assert [(l.id, l.website) for l in ls[8:]] == [(51, "https://a"), (-52, "https://c")]


def test_query_stays_in_bbox_and_tourism_list():
    q = lodgings_query(BLACK_FOREST_BBOX)
    assert "47.55,7.55,48.95,8.8" in q and "out center" in q
    for kind in (
        "hotel",
        "guest_house",
        "hostel",
        "alpine_hut",
        "wilderness_hut",
        "chalet",
        "apartment",
        "camp_site",
    ):
        assert f'["tourism"="{kind}"]' in q
    assert "museum" not in q


@respx.mock
def test_fetch_lodgings_raises_on_overpass_failure():
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(502))
    with make_http_client(5) as http, pytest.raises(OverpassError):
        fetch_lodgings(OverpassClient(http, backoff_s=0), BLACK_FOREST_BBOX, pause_s=0)


@respx.mock
def test_fetch_lodgings_raises_on_200_with_timeout_remark():
    """A tile that timed out server-side must not count as 'no lodgings here'."""
    body = {"elements": [], "remark": "runtime error: Query timed out in \"query\" at line 1."}
    respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=body))
    with make_http_client(5) as http, pytest.raises(OverpassError):
        fetch_lodgings(OverpassClient(http, backoff_s=0), BLACK_FOREST_BBOX, pause_s=0)


def _trail(conn):
    upsert_source(conn, SRC)
    upsert_trail(
        conn,
        id=TRAIL,
        name="T",
        kind="day_hike", region="black_forest",
        roundtrip=False,
        osm_relation_id=None,
        length_km=7.4,
        ascent_m=0,
        descent_m=0,
        profile=[(0.0, 500.0)],
        line=LINE,
        source_id=SRC.id,
    )


def insert_lodging(conn, id, lat, lon):
    upsert_lodging(
        conn, Lodging(id=id, name=f"L{id}", kind="hotel", website=None, lat=lat, lon=lon), SRC.id
    )


@pytest.fixture
def trail_on_line_48_8(conn):
    _trail(conn)


def _links(conn):
    return conn.execute(
        "select lodging_id, dist_m, along_km from trail_lodgings where trail_id = %s\n and abs(lodging_id) between 9000000 and 9000999 order by 1",
        [TRAIL],
    ).fetchall()


@pytest.mark.db
def test_trail_lodgings_within_2km(conn, trail_on_line_48_8):
    insert_lodging(conn, 9000101, 48.009, 8.05)  # ~1 km north
    insert_lodging(conn, 9000102, 48.027, 8.05)  # ~3 km north
    link_trail_lodgings(conn)
    rows = _links(conn)
    assert [r[0] for r in rows] == [9000101] and 900 < rows[0][1] < 1100


@pytest.mark.db
def test_along_km_is_plausible(conn, trail_on_line_48_8):
    insert_lodging(conn, 9000103, 48.001, 8.05)  # halfway
    insert_lodging(conn, 9000104, 48.001, 8.0)  # at start
    link_trail_lodgings(conn)
    rows = {r[0]: float(r[2]) for r in _links(conn)}
    assert abs(rows[9000103] - 3.7) < 0.1
    assert rows[9000104] < 0.1


@pytest.mark.db
def test_along_km_counts_metres_not_degrees(conn):
    upsert_source(conn, SRC)
    upsert_l_trail(conn, TRAIL, SRC.id)
    insert_lodging(conn, 9000106, 48.05, 8.0)  # at the corner of the L
    link_trail_lodgings(conn)
    rows = {r[0]: float(r[2]) for r in _links(conn)}
    assert abs(rows[9000106] - L_CORNER_KM) < 0.05  # degree fraction: 4,46 km


@pytest.mark.db
def test_import_is_idempotent(conn, trail_on_line_48_8):
    data = {
        "elements": [
            {
                "type": "node",
                "id": 9000105,
                "lat": 48.005,
                "lon": 8.02,
                "tags": {"tourism": "hotel", "name": "A"},
            },
            {
                "type": "way",
                "id": 9000106,
                "center": {"lat": 48.005, "lon": 8.03},
                "tags": {"tourism": "hostel", "name": "B"},
            },
        ]
    }
    lodgings = parse_lodgings(data)
    for _ in range(2):
        import_lodgings(conn, lodgings, SRC)
    n = conn.execute("select count(*) from lodgings where id in (9000105, -9000106)").fetchone()[0]
    assert n == 2
    assert [r[0] for r in _links(conn)] == [-9000106, 9000105]


@pytest.mark.db
def test_stage_count_covers_every_long_distance_trail(conn):
    from hikeall.cli import STAGE_COUNT_SQL
    from hikeall.db import upsert_stage

    upsert_source(conn, SRC)
    for tid, kind in (("test-lodg-mittelweg", "long_distance"), ("test-lodg-day", "day_hike")):
        upsert_trail(
            conn, id=tid, name=tid, kind=kind, region="black_forest", roundtrip=False, osm_relation_id=None,
            length_km=7.4, ascent_m=0, descent_m=0, profile=[(0.0, 500.0)], line=LINE,
            source_id=SRC.id,
        )
        upsert_stage(
            conn, id=f"{tid}-01", trail_id=tid, seq=1, name="A – B", start_name="A",
            end_name="B", length_km=7.4, ascent_m=0, descent_m=0, profile=[(0.0, 500.0)],
            line=LINE, source_id=SRC.id,
        )
    insert_lodging(conn, 9000201, 48.005, 8.05)  # ~0.5 km from LINE
    rows = {r[0]: r[3] for r in conn.execute(STAGE_COUNT_SQL).fetchall()}
    assert rows["test-lodg-mittelweg-01"] >= 1
    assert "test-lodg-day-01" not in rows


def test_collect_lodgings_unions_regions(monkeypatch):
    from hikeall import regions as R
    from hikeall.ingest import lodgings as mod

    def fake(overpass, bbox, *a, **k):
        shared = Lodging(id=1, name="Grenzhotel", kind="hotel", lat=48.9, lon=8.0)
        own = Lodging(id=int(bbox.south * 100), name="x", kind="hotel", lat=bbox.south, lon=8.0)
        return [shared, own]

    monkeypatch.setattr(mod, "fetch_lodgings", fake)
    reported = []
    out = mod.collect_lodgings(None, R.REGIONS, lambda r, n: reported.append((r.id, n)))
    assert len(out) == 4 and len({x.id for x in out}) == 4
    assert [n for _, n in reported] == [2, 2, 2]


def test_collect_lodgings_from_pbf_where_complete(monkeypatch):
    from hikeall import regions as R
    from hikeall.adapters import osm_pbf
    from hikeall.ingest import lodgings as mod

    asked = []
    monkeypatch.setattr(mod, "fetch_lodgings", lambda o, bbox, *a, **k: asked.append(bbox) or [])
    hotel = {"type": "node", "id": 5, "lat": 48.0, "lon": 8.0,
             "tags": {"tourism": "hotel", "name": "Hotel PBF"}}
    monkeypatch.setattr(
        osm_pbf, "read_regions", lambda d, regions, what: {"black_forest": {"elements": [hotel]}}
    )
    out = mod.collect_lodgings(None, R.REGIONS, pbf_dir=Path("osm"))
    assert [x.name for x in out] == ["Hotel PBF"]
    assert len(asked) == 2  # palatinate and lake_constance via Overpass
