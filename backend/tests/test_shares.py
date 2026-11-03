import httpx
import pytest
import respx
from conftest import Ramp
from test_day_hikes import OSM, RELATIONS

from hikesense.adapters.http import make_http_client
from hikesense.adapters.overpass import OVERPASS_URL, OverpassClient
from hikesense.ingest.day_hikes import Candidate, import_day_hikes
from hikesense.ingest.shares import (
    classify_surface,
    classify_way_type,
    compute_shares,
    import_shares,
    member_way_lengths,
    way_tags_query,
)


def test_classify_surface():
    assert classify_surface({"surface": "asphalt"}) == "paved"
    assert classify_surface({"surface": "fine_gravel"}) == "gravel"
    assert classify_surface({"surface": "ground"}) == "unpaved"
    assert classify_surface({}) == "unknown"


def test_classify_way_type():
    assert classify_way_type({"highway": "footway"}) == "path"
    assert classify_way_type({"highway": "track"}) == "track"
    assert classify_way_type({"highway": "tertiary"}) == "road"
    assert classify_way_type({"highway": "cycleway"}) == "cycleway"
    assert classify_way_type({"highway": "pedestrian"}) == "other"
    assert classify_way_type({}) == "unknown"


def test_compute_shares_weights_by_length():
    surface, way = compute_shares(
        [(1, 3.0), (2, 1.0)],
        {1: {"surface": "asphalt", "highway": "track"}, 2: {"highway": "path"}},
    )
    assert surface == {"paved": 0.75, "unknown": 0.25}
    assert way == {"track": 0.75, "path": 0.25}


def test_compute_shares_empty_is_empty():
    assert compute_shares([], {}) == ({}, {})


def test_way_tags_query():
    q = way_tags_query([1, 22])
    assert "relation(id:1,22);" in q and "way(r);" in q and "out tags;" in q


def test_member_way_lengths_uses_route_roles_only():
    pts = [{"lat": 48.0, "lon": 8.0}, {"lat": 48.0, "lon": 8.01}]
    data = {
        "elements": [
            {
                "type": "relation",
                "id": 5,
                "members": [
                    {"type": "way", "ref": 10, "role": "", "geometry": pts},
                    {"type": "way", "ref": 11, "role": "alternative", "geometry": pts},
                    {"type": "node", "ref": 12, "role": ""},
                ],
            }
        ]
    }
    res = member_way_lengths(data, 5)
    assert [w for w, _ in res] == [10] and res[0][1] == pytest.approx(0.744, abs=0.01)
    with pytest.raises(ValueError):
        member_way_lengths(data, 6)


def _mock(way_elements, fail_tags=False):
    def handler(request):
        query = httpx.QueryParams(request.content.decode()).get("data")
        if "way(r)" in query:
            if fail_tags:
                return httpx.Response(200, json={"elements": [], "remark": "runtime error"})
            return httpx.Response(200, json={"elements": way_elements})
        ids = {int(i) for i in query.split("relation(id:")[1].split(")")[0].split(",")}
        return httpx.Response(200, json={"elements": [r for r in RELATIONS if r["id"] in ids]})

    return handler


def _client(handler):
    respx.post(OVERPASS_URL).side_effect = handler
    return OverpassClient(make_http_client(5), backoff_s=0)


WAYS = [
    {"type": "way", "id": 1, "tags": {"surface": "asphalt", "highway": "residential"}},
    {"type": "way", "id": 2, "tags": {"surface": "ground", "highway": "path"}},
    {"type": "way", "id": 3, "tags": {"highway": "track"}},
    {"type": "way", "id": 4, "tags": {"surface": "gravel", "highway": "track"}},
]


@pytest.mark.db
@respx.mock
def test_shares_stored(conn):
    client = _client(_mock(WAYS))
    cands = [Candidate(2001, "Rundweg A", 8.9, True, "accepted", "automatisch")]
    import_day_hikes(conn, cands, client, Ramp(), source=OSM)
    row = conn.execute(
        "select surface_shares, way_type_shares from trails where id='day-2001'"
    ).fetchone()
    assert abs(sum(row[0].values()) - 1) < 0.01 and abs(sum(row[1].values()) - 1) < 0.01
    assert set(row[0]) == {"paved", "unpaved", "unknown", "gravel"}


@pytest.mark.db
@respx.mock
def test_import_shares_writes_only_share_columns_and_reports_failures(conn):
    client = _client(_mock(WAYS))
    cands = [Candidate(2001, "Rundweg A", 8.9, True, "accepted", "automatisch")]
    import_day_hikes(conn, cands, client, Ramp(), source=OSM)
    conn.execute("update trails set surface_shares = null, way_type_shares = null")
    rep = import_shares(conn, client, {"day-2001": [2001], "day-2003": [2003]}, batch_size=1)
    assert "day-2001" in rep.updated and not rep.failed
    assert conn.execute(
        "select surface_shares is not null, name from trails where id='day-2001'"
    ).fetchone() == (True, "Rundweg A")

    # all ways unknown -> listed as mostly unknown, not silent
    client2 = _client(_mock([]))
    rep = import_shares(conn, client2, {"day-2001": [2001]})
    assert rep.mostly_unknown() == [("day-2001", 1.0)]

    # Overpass remark -> that trail fails, nothing written
    client3 = _client(_mock(WAYS, fail_tags=True))
    rep = import_shares(conn, client3, {"day-2001": [2001]})
    assert rep.failed and "OverpassError" in rep.failed[0][1] and not rep.updated


@pytest.mark.db
@respx.mock
def test_cli_import_shares_only_unknown_trail_exits_2(conn, monkeypatch, capsys):
    from hikesense import cli

    monkeypatch.setenv("SUPABASE_DB_URL", conn.info.dsn + " password=postgres")
    assert cli.main(["import-shares", "--only", "no-such-trail-zz"]) == 2
    assert "no-such-trail-zz" in capsys.readouterr().err
