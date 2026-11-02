from datetime import date

import httpx
import pytest
import respx
from conftest import Ramp

from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OVERPASS_URL, OverpassClient
from hikeall.errors import OverpassError
from hikeall.ingest.assemble import orient_by_members
from hikeall.ingest.day_hikes import (
    Candidate,
    auto_decision,
    final_decision,
    import_day_hikes,
    is_roundtrip,
    read_candidates,
    scan,
    set_manual,
    tiles,
    write_candidates,
)
from hikeall.models import BBox, Source
from hikeall.regions import REGIONS, Region, get_region

OSM = Source(
    id="test-osm-day",
    name="test osm",
    url="https://example.org/osm",
    license="ODbL",
    retrieved_at=date(2026, 10, 28),
)
AREA = BBox(south=47.9, west=7.9, north=48.1, east=8.1)
AREA_REGION = (Region("test", "Test", AREA, ("DE",), ()),)

# A closed ~8.9 km square loop starting at its south-west corner, cut into four ways.
SW, SE, NE, NW = (48.0, 8.0), (48.0, 8.03), (48.02, 8.03), (48.02, 8.0)


def _edge(a, b, n=10):
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def _way(ref, pts, role=""):
    return {
        "type": "way",
        "ref": ref,
        "role": role,
        "geometry": [{"lat": a, "lon": b} for a, b in pts],
    }


def _rel(rid, tags, ways):
    return {"type": "relation", "id": rid, "tags": {"route": "hiking", **tags}, "members": ways}


LOOP_WAYS = [
    _way(1, _edge(SW, SE)),
    _way(2, _edge(NE, SE)),  # stored against walking direction
    _way(3, _edge(NE, NW)),
    _way(4, _edge(NW, SW)),
]
LINE_WAYS = [
    _way(5, _edge((48.05, 8.0), (48.05, 8.04))),
    _way(6, _edge((48.05, 8.04), (48.05, 8.08))),
]
GAP_WAYS = [
    _way(7, _edge((48.07, 8.0), (48.07, 8.04))),
    _way(8, _edge((48.07, 8.05), (48.07, 8.1))),
]

RELATIONS = [
    _rel(2001, {"name": "Rundweg A", "network": "lwn"}, LOOP_WAYS),
    _rel(2002, {"network": "lwn"}, LOOP_WAYS),
    _rel(2003, {"name": "Strecke B", "network": "lwn"}, LINE_WAYS),
    _rel(2004, {"name": "Lückenweg", "network": "lwn"}, GAP_WAYS),
    _rel(2005, {"name": "Fernweg", "network": "nwn"}, LINE_WAYS),
    _rel(2006, {"name": "A - B", "network": "lwn", "network:type": "node_network"}, LINE_WAYS),
]


def _tags_only(rels):
    return {"elements": [{"type": "relation", "id": r["id"], "tags": r["tags"]} for r in rels]}


def _overpass_mock(relations, fail_ids=(), abroad_ids=None):
    """Answer tag queries with tags, `relation(id:...)` queries with geometry and foreign-country
    queries (`area[...]`) with those of `abroad_ids[<area value>]` that were asked for."""

    def handler(request):
        query = httpx.QueryParams(request.content.decode()).get("data")
        if "area[" in query:
            ids = {int(i) for i in query.split("relation(id:")[1].split(")")[0].split(",")}
            area = query.split('area["')[1].split('"="')[1].split('"')[0]
            hit = [
                {"type": "relation", "id": i}
                for i in sorted(ids & set((abroad_ids or {}).get(area, ())))
            ]
            return httpx.Response(200, json={"elements": hit})
        if "out tags" in query:
            return httpx.Response(200, json=_tags_only(relations))
        ids = {int(i) for i in query.split("relation(id:")[1].split(")")[0].split(",")}
        if ids & set(fail_ids):
            return httpx.Response(400)
        return httpx.Response(200, json={"elements": [r for r in relations if r["id"] in ids]})

    return handler


@pytest.fixture
def overpass():
    with respx.mock:
        route = respx.post(OVERPASS_URL)
        route.side_effect = _overpass_mock(RELATIONS)
        with make_http_client(5) as http:
            yield route, OverpassClient(http, backoff_s=0)


# --- auto decision -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "args,expected",
    [
        ((None, 12, False, "lwn"), "rejected"),
        (("Rundweg A", 12, True, "lwn"), "rejected"),
        (("Rundweg A", 3.9, False, "lwn"), "rejected"),
        (("Westweg", 285, False, "iwn"), "rejected"),
        (("Rundweg A", 12, False, "lwn"), "accepted"),
    ],
)
def test_auto_decision(args, expected):
    assert auto_decision(*args)[0] == expected


@pytest.mark.parametrize(
    "args,reason",
    [
        ((None, 12, False, "lwn"), "kein Name"),
        (("", 12, False, "lwn"), "kein Name"),
        (("A", 12, True, "lwn"), "Lücken im Verlauf"),
        (("A", 30.5, False, "lwn"), "Länge außerhalb 5–30 km"),
        (("A", 12, False, "nwn"), "Fernweg, kein Tagesziel"),
        (("A", 5, False, None), "automatisch"),
        (("A", 30, False, "rwn"), "automatisch"),
    ],
)
def test_auto_decision_reasons(args, reason):
    assert auto_decision(*args)[1] == reason


# --- roundtrip and orientation -------------------------------------------------------------


def test_roundtrip_from_osm_tag():
    line = _edge((48.05, 8.0), (48.05, 8.04))  # ends ~3 km apart
    assert is_roundtrip({"roundtrip": "yes"}, line)
    assert not is_roundtrip({}, line)


def test_roundtrip_from_start_end_distance_below_300_m():
    assert is_roundtrip({}, [(48.0, 8.0), (48.01, 8.0), (48.0, 8.0035)])  # ~260 m apart
    assert not is_roundtrip({}, [(48.0, 8.0), (48.01, 8.0), (48.0, 8.0045)])  # ~335 m apart


def test_orientation_follows_member_order_on_a_line():
    a, b = _edge((48.0, 8.0), (48.0, 8.01)), _edge((48.0, 8.01), (48.0, 8.02))
    assert orient_by_members(b[::-1] + a[::-1][1:], [a, b])[0] == (48.0, 8.0)
    assert orient_by_members(a + b[1:], [a, b])[0] == (48.0, 8.0)


def test_loop_starts_at_first_member_and_runs_in_member_order():
    segs = [[(g["lat"], g["lon"]) for g in w["geometry"]] for w in LOOP_WAYS]
    reversed_loop = _edge(NE, SE) + _edge(SE, SW)[1:] + _edge(SW, NW)[1:] + _edge(NW, NE)[1:]
    line = orient_by_members(reversed_loop, segs)
    assert line[0] == pytest.approx(SW) and line[-1] == pytest.approx(SW)
    # SW → SE → NE → NW → SW
    assert line[10] == pytest.approx(SE) and line[20] == pytest.approx(NE)
    assert len(line) == len(reversed_loop)


# --- scanning ------------------------------------------------------------------------------


def test_tiles_cover_bbox_without_overlap():
    ts = tiles(BBox(south=47.55, west=7.55, north=48.95, east=8.75), step_deg=0.35)
    assert len(ts) == 16
    assert ts[0].south == 47.55 and ts[-1].north == 48.95 and ts[-1].east == 8.75


def test_scan_builds_candidates_with_auto_decisions(overpass):
    route, client = overpass
    res = scan(client, AREA_REGION, step_deg=0.1, pause_s=0)
    cands = {c.osm_relation_id: c for c in res.candidates}
    assert set(cands) == {2001, 2002, 2003, 2004, 2005}  # node-network segment left out
    assert res.skipped_segments == 1
    assert len(route.calls) == 4 + 1  # four tag tiles (relations deduplicated), one geometry batch
    geometry_query = httpx.QueryParams(route.calls[-1].request.content.decode()).get("data")
    assert "relation(id:2001,2003,2004)" in geometry_query  # tag-rejected rows need no geometry
    loop = cands[2001]
    assert (loop.auto_decision, loop.auto_reason) == ("accepted", "automatisch")
    assert loop.roundtrip is True and loop.length_km == pytest.approx(8.9, abs=0.1)
    assert cands[2002].auto_reason == "kein Name" and cands[2002].length_km is None
    assert cands[2003].roundtrip is False and cands[2003].auto_decision == "accepted"
    assert cands[2004].auto_reason == "Lücken im Verlauf"
    assert cands[2005].auto_reason == "Fernweg, kein Tagesziel" and cands[2005].length_km is None


def test_scan_rejects_relation_leaving_the_bbox():
    far = _rel(2010, {"name": "Grenzweg"}, [_way(9, _edge((48.0, 7.5), (48.0, 7.6)))])
    with respx.mock:
        respx.post(OVERPASS_URL).side_effect = _overpass_mock([far])
        with make_http_client(5) as http:
            [c] = scan(OverpassClient(http, backoff_s=0), AREA_REGION, pause_s=0).candidates
    assert c.auto_decision == "rejected" and "keiner Region" in c.auto_reason


def _scan_all(relations, **kw):
    with respx.mock:
        route = respx.post(OVERPASS_URL)
        route.side_effect = _overpass_mock(relations, **kw)
        with make_http_client(5) as http:
            res = scan(OverpassClient(http, backoff_s=0), REGIONS, pause_s=0)
    return {c.osm_relation_id: c for c in res.candidates}, route


def _loop_rel(rid, centre, name="Runde"):
    lat, lon = centre
    sw, se = (lat, lon), (lat, lon + 0.03)
    ne, nw = (lat + 0.02, lon + 0.03), (lat + 0.02, lon)
    ways = [
        _way(1, _edge(sw, se)),
        _way(2, _edge(se, ne)),
        _way(3, _edge(ne, nw)),
        _way(4, _edge(nw, sw)),
    ]
    return _rel(rid, {"name": name, "network": "lwn"}, ways)


def test_scan_assigns_region():
    rels = [
        _loop_rel(3001, (48.0, 8.0)),
        _loop_rel(3002, (49.3, 7.9)),
        _loop_rel(3003, (47.6, 9.3)),
    ]
    cands, _ = _scan_all(rels)
    assert {rid: c.region for rid, c in cands.items()} == {
        3001: "black_forest",
        3002: "palatinate",
        3003: "lake_constance",
    }
    assert all(c.auto_decision == "accepted" for c in cands.values())


def test_route_in_no_region_rejected():
    rel = _rel(3010, {"name": "Quer"}, [_way(9, _edge((48.91, 8.0), (48.99, 8.0)))])
    cands, _ = _scan_all([rel])
    c = cands[3010]
    assert c.auto_decision == "rejected" and c.auto_reason == "liegt in keiner Region vollständig"
    assert c.region is None


def test_palatinate_route_into_france_rejected():
    rels = [
        _loop_rel(3020, (49.3, 7.9), "Grenzrunde"),
        _loop_rel(3021, (49.35, 7.95), "Pfalzrunde"),
        _loop_rel(3022, (47.6, 9.3), "Seerunde"),
    ]
    cands, route = _scan_all(rels, abroad_ids={"FR": (3020, 3022)})
    assert (cands[3020].auto_decision, cands[3020].auto_reason) == (
        "rejected",
        "führt nach Frankreich",
    )
    assert cands[3021].auto_decision == "accepted"
    assert cands[3022].auto_decision == "accepted"  # Lake Constance has no foreign check
    queries = [httpx.QueryParams(c.request.content.decode()).get("data") for c in route.calls]
    foreign = [q for q in queries if "area[" in q]
    assert len(foreign) == 3  # one per exclusion area of the Palatinate
    assert '"ISO3166-1"="FR"' in foreign[0] and "3022" not in "".join(foreign)
    assert "3020" not in foreign[1]  # already rejected: not asked again


def test_palatinate_route_in_baden_rejected_hesse_and_rlp():
    rels = [
        _loop_rel(3030, (49.0, 8.3), "Rheinebene"),
        _loop_rel(3031, (49.5, 8.3), "Hessenrunde"),
        _loop_rel(3032, (49.35, 7.95), "Pfalzrunde"),
    ]
    cands, _ = _scan_all(rels, abroad_ids={"DE-BW": (3030,), "DE-HE": (3031,)})
    assert cands[3030].auto_reason == "liegt in Baden-Württemberg, nicht im Pfälzerwald"
    assert cands[3031].auto_reason == "liegt in Hessen, nicht im Pfälzerwald"
    assert cands[3032].auto_decision == "accepted"
    assert {c.auto_decision for c in (cands[3030], cands[3031])} == {"rejected"}


def test_scan_rejects_stage_relation_of_curated_long_distance_trail():
    from hikeall.ingest.day_hikes import curated_relation_ids

    stage = next(iter(curated_relation_ids() - {1}))
    assert 8124459 in curated_relation_ids() and 56369 in curated_relation_ids()  # incl. groups
    cands, _ = _scan_all([_loop_rel(stage, (48.0, 8.0), "Etappe"), _loop_rel(3040, (48.0, 8.0))])
    assert (cands[stage].auto_decision, cands[stage].auto_reason) == (
        "rejected",
        "Etappe eines Fernwegs",
    )
    assert cands[3040].auto_decision == "accepted"


def test_auto_decision_stage_relation():
    assert auto_decision("Etappe", 12, False, "lwn", 5, {5}) == ("rejected", "Etappe eines Fernwegs")
    assert auto_decision("Etappe", 12, False, "lwn", 6, {5})[0] == "accepted"


def test_old_csv_without_region_keeps_manual_decisions(tmp_path):
    csv = tmp_path / "d.csv"
    csv.write_text(
        "osm_relation_id,name,length_km,roundtrip,auto_decision,auto_reason,"
        "manual_decision,manual_reason\n"
        "3001,Runde,8.90,true,accepted,automatisch,rejected,Weg gesperrt\n",
        encoding="utf-8",
    )
    assert read_candidates(csv)[0].region == "black_forest"
    cands, _ = _scan_all([_loop_rel(3001, (48.0, 8.0))])
    write_candidates(csv, list(cands.values()))
    [row] = read_candidates(csv)
    assert row.region == "black_forest"
    assert (row.manual_decision, row.manual_reason) == ("rejected", "Weg gesperrt")
    assert csv.read_text(encoding="utf-8").splitlines()[0].startswith("osm_relation_id,region,")


def test_scan_single_region_keeps_other_rows(tmp_path):
    csv = tmp_path / "d.csv"
    write_candidates(
        csv,
        [
            Candidate(1, "A", 10, True, "accepted", "automatisch", region="black_forest"),
            Candidate(2, "B", 10, True, "accepted", "automatisch", region="palatinate"),
        ],
    )
    before = {c.osm_relation_id: c for c in read_candidates(csv)}
    rels = [_loop_rel(3, (49.3, 7.9))]
    with respx.mock:
        respx.post(OVERPASS_URL).side_effect = _overpass_mock(rels)
        with make_http_client(5) as http:
            res = scan(OverpassClient(http, backoff_s=0), (get_region("palatinate"),), pause_s=0)
    write_candidates(csv, res.candidates, {"palatinate"})
    after = {c.osm_relation_id: c for c in read_candidates(csv)}
    assert after[1] == before[1]  # Black Forest row untouched, not marked as gone
    assert after[2].auto_reason == "nicht mehr in OSM gefunden (letzter Scan)"
    assert after[3].region == "palatinate"


def test_gap_and_no_way_relations_keep_the_region_they_were_seen_in():
    gap = _rel(3030, {"name": "Lücke", "network": "lwn"}, GAP_WAYS)  # lat 48.07: Black Forest
    empty = _rel(3031, {"name": "Leer", "network": "lwn"}, [])
    cands, _ = _scan_all([gap, empty])
    assert cands[3030].auto_reason == "Lücken im Verlauf"
    assert cands[3031].auto_reason == "keine Wege in der Relation"
    assert cands[3030].region == "black_forest" and cands[3031].region == "black_forest"


def test_cli_region_scan_summary_ignores_other_regions(monkeypatch, capsys, tmp_path):
    from hikeall import cli
    from hikeall.config import Settings

    csv = tmp_path / "d.csv"
    write_candidates(
        csv, [Candidate(1, "A", 10, True, "accepted", "automatisch", region="black_forest")]
    )
    monkeypatch.setattr(cli, "_settings", lambda: Settings(supabase_db_url="postgresql://x"))
    with respx.mock:
        respx.post(OVERPASS_URL).side_effect = _overpass_mock([_loop_rel(3, (49.3, 7.9))])
        assert cli.main(["scan-day-hikes", "--csv", str(csv), "--region", "palatinate"]) == 0
    out = capsys.readouterr().out
    assert "1 neu, 0 nicht mehr in OSM" in out


def test_scan_fails_cleanly_when_overpass_fails():
    with respx.mock:
        respx.post(OVERPASS_URL).mock(return_value=httpx.Response(504))
        with make_http_client(5) as http, pytest.raises(OverpassError):
            scan(OverpassClient(http, backoff_s=0), AREA_REGION, pause_s=0)


# --- CSV -----------------------------------------------------------------------------------


def test_rescan_keeps_manual_decisions(tmp_path):
    csv = tmp_path / "d.csv"
    write_candidates(csv, [Candidate(1, "A", 10, True, "accepted", "automatisch")])
    set_manual(csv, 1, "rejected", "Weg gesperrt")
    write_candidates(csv, [Candidate(1, "A", 10.2, True, "accepted", "automatisch")])
    assert final_decision(read_candidates(csv)[0]) == ("rejected", "Weg gesperrt")


def test_csv_round_trip_keeps_all_columns(tmp_path):
    csv = tmp_path / "d.csv"
    rows = [
        Candidate(7, "Weg, mit Komma", 12.346, False, "accepted", "automatisch", "", ""),
        Candidate(3, None, None, None, "rejected", "kein Name", "accepted", "Vorschlag: ja"),
    ]
    write_candidates(csv, rows)
    assert csv.read_text(encoding="utf-8").splitlines()[0] == (
        "osm_relation_id,region,name,length_km,roundtrip,auto_decision,auto_reason,"
        "manual_decision,manual_reason"
    )
    back = read_candidates(csv)
    assert [c.osm_relation_id for c in back] == [3, 7]  # sorted by id
    assert back[1] == Candidate(7, "Weg, mit Komma", 12.35, False, "accepted", "automatisch")
    assert back[0] == rows[1]


def test_rescan_keeps_rows_that_disappeared_from_osm(tmp_path):
    csv = tmp_path / "d.csv"
    write_candidates(
        csv,
        [
            Candidate(1, "A", 10, True, "accepted", "automatisch"),
            Candidate(2, "B", 11, False, "accepted", "automatisch"),
        ],
    )
    set_manual(csv, 2, "accepted", "schöne Aussicht")
    write_candidates(csv, [Candidate(1, "A", 10, True, "accepted", "automatisch")])
    rows = {c.osm_relation_id: c for c in read_candidates(csv)}
    assert set(rows) == {1, 2}
    gone = rows[2]
    assert (gone.manual_decision, gone.manual_reason) == ("accepted", "schöne Aussicht")
    assert gone.auto_decision == "rejected" and "nicht mehr in OSM" in gone.auto_reason
    assert gone.name == "B" and gone.length_km == 11


def test_set_manual_rejects_unknown_id_and_bad_decision(tmp_path):
    csv = tmp_path / "d.csv"
    write_candidates(csv, [Candidate(1, "A", 10, True, "accepted", "automatisch")])
    with pytest.raises(ValueError, match="99"):
        set_manual(csv, 99, "rejected", "x")
    with pytest.raises(ValueError):
        set_manual(csv, 1, "maybe", "x")


def test_manual_decision_wins_and_empty_falls_back_to_auto():
    c = Candidate(1, "A", 10, True, "rejected", "Länge außerhalb 5–30 km")
    assert final_decision(c) == ("rejected", "Länge außerhalb 5–30 km")
    c.manual_decision, c.manual_reason = "accepted", "trotzdem"
    assert final_decision(c) == ("accepted", "trotzdem")


# --- import --------------------------------------------------------------------------------


def _cands(manual=None):
    manual = manual or {}
    rows = [
        Candidate(2001, "Rundweg A", 8.9, True, "accepted", "automatisch"),
        Candidate(2002, None, 8.9, True, "rejected", "kein Name"),
        Candidate(2003, "Strecke B", 5.9, False, "accepted", "automatisch"),
        Candidate(2004, "Lückenweg", 7.0, False, "rejected", "Lücken im Verlauf"),
    ]
    for c in rows:
        if c.osm_relation_id in manual:
            c.manual_decision, c.manual_reason = manual[c.osm_relation_id]
    return rows


def _day_hikes(conn):
    return conn.execute(
        "select id, name, roundtrip, source_id from trails "
        "where kind = 'day_hike' and id like 'day-200%%' order by id"
    ).fetchall()


@pytest.mark.db
def test_import_writes_only_accepted_day_hikes(conn, overpass):
    _, client = overpass
    rep = import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    assert [r.trail_id for r in rep.imported] == ["day-2001", "day-2003"] and not rep.failed
    assert _day_hikes(conn) == [
        ("day-2001", "Rundweg A", True, OSM.id),
        ("day-2003", "Strecke B", False, OSM.id),
    ]
    row = conn.execute(
        "select osm_relation_id, length_km, ascent_m, st_npoints(geom) from trails "
        "where id = 'day-2001'"
    ).fetchone()
    assert row[0] == 2001 and float(row[1]) == pytest.approx(8.9, abs=0.1) and row[3] >= 41


@pytest.mark.db
def test_manually_rejected_rows_are_never_imported_and_are_removed(conn, overpass):
    _, client = overpass
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    rep = import_day_hikes(
        conn, _cands({2003: ("rejected", "Weg gesperrt")}), client, Ramp(), source=OSM
    )
    assert [r.trail_id for r in rep.imported] == ["day-2001"]
    assert rep.removed == ["day-2003"]
    assert [r[0] for r in _day_hikes(conn)] == ["day-2001"]


@pytest.mark.db
def test_manual_accept_overrides_auto_reject_and_failure_is_reported(conn, overpass):
    _, client = overpass
    rep = import_day_hikes(
        conn, _cands({2004: ("accepted", "Lücke egal")}), client, Ramp(), source=OSM
    )
    assert [r.trail_id for r in rep.imported] == ["day-2001", "day-2003"]
    assert len(rep.failed) == 1 and rep.failed[0][0] == 2004 and "GapError" in rep.failed[0][1]


@pytest.mark.db
def test_import_sets_trail_region(conn):
    rel = _loop_rel(2090, (49.3, 7.9), "Pfalzrunde")
    cand = Candidate(2090, "Pfalzrunde", 8.9, True, "accepted", "automatisch", region="palatinate")
    with respx.mock:
        respx.post(OVERPASS_URL).side_effect = _overpass_mock([rel])
        with make_http_client(5) as http:
            res = import_day_hikes(
                conn, [cand], OverpassClient(http, backoff_s=0), Ramp(), source=OSM
            )
    assert not res.failed
    assert conn.execute("select region from trails where id = 'day-2090'").fetchone()[0] == (
        "palatinate"
    )


def test_reimport_is_idempotent(conn, overpass):
    _, client = overpass
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    first = conn.execute("select * from trails where id like 'day-200%%' order by id").fetchall()
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    again = conn.execute("select * from trails where id like 'day-200%%' order by id").fetchall()
    assert again == first and len(again) == 2


@pytest.mark.db
def test_failed_overpass_batch_is_reported_per_relation_and_rest_continues(conn):
    with respx.mock:
        respx.post(OVERPASS_URL).side_effect = _overpass_mock(RELATIONS, fail_ids=[2001])
        with make_http_client(5) as http:
            client = OverpassClient(http, backoff_s=0)
            rep = import_day_hikes(conn, _cands(), client, Ramp(), source=OSM, batch_size=1)
    assert [r.trail_id for r in rep.imported] == ["day-2003"]
    assert [f[0] for f in rep.failed] == [2001]


@pytest.mark.db
def test_one_bad_relation_does_not_abort_the_batch(conn, overpass, monkeypatch):
    from hikeall.ingest import day_hikes

    real = day_hikes.upsert_trail

    def flaky(c, **kw):
        if kw["id"] == "day-2001":
            c.execute("select 1/0")  # a real database error inside the transaction
        real(c, **kw)

    monkeypatch.setattr(day_hikes, "upsert_trail", flaky)
    _, client = overpass
    rep = import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    assert [r.trail_id for r in rep.imported] == ["day-2003"]
    assert rep.failed[0][0] == 2001 and "DivisionByZero" in rep.failed[0][1]
    assert [r[0] for r in _day_hikes(conn)] == ["day-2003"]


@pytest.mark.db
def test_cli_import_reports_failed_relation_and_exits_1(conn, monkeypatch, capsys, tmp_path):
    from hikeall import cli
    from hikeall.ingest.day_hikes import DayHikeImport

    csv = tmp_path / "d.csv"
    write_candidates(csv, _cands())

    def fake(*_a, **_kw):
        return DayHikeImport(imported=[], failed=[(2001, "GapError: gap of 900 m")], removed=[])

    monkeypatch.setenv("SUPABASE_DB_URL", conn.info.dsn + " password=postgres")
    monkeypatch.setattr(cli, "import_day_hikes", fake)
    assert cli.main(["import-day-hikes", "--csv", str(csv)]) == 1
    err = capsys.readouterr().err
    assert "2001" in err and "GapError" in err


@pytest.mark.db
def test_import_records_the_elevation_source(conn, overpass):
    _, client = overpass
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    assert conn.execute("select 1 from sources where id = 'copernicus-glo30'").fetchone()


@pytest.mark.db
def test_rejected_day_hike_with_commons_photos_is_removed_with_its_photos(conn, overpass):
    _, client = overpass
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    conn.execute(
        "insert into photos (trail_id, source, url, author, license) "
        "values ('day-2003', 'commons', 'https://example.org/p.jpg', 'Tester', 'CC BY 4.0')"
    )
    rep = import_day_hikes(
        conn, _cands({2003: ("rejected", "Weg gesperrt")}), client, Ramp(), source=OSM
    )
    assert rep.failed == []
    assert rep.removed == ["day-2003"]
    assert [r[0] for r in _day_hikes(conn)] == ["day-2001"]
    assert (
        conn.execute("select count(*) from photos where trail_id = 'day-2003'").fetchone()[0] == 0
    )


@pytest.mark.db
def test_rejected_day_hike_with_own_upload_fails_loudly_and_rest_continues(conn, overpass):
    _, client = overpass
    import_day_hikes(conn, _cands(), client, Ramp(), source=OSM)
    conn.execute(
        "insert into photos (trail_id, source, url, author, license) values "
        "('day-2003', 'commons', 'https://example.org/c.jpg', 'Tester', 'CC BY 4.0'),"
        "('day-2003', 'upload', 'https://example.org/u.jpg', 'Ali', 'privat')"
    )
    rep = import_day_hikes(
        conn, _cands({2003: ("rejected", "Weg gesperrt")}), client, Ramp(), source=OSM
    )
    assert [r.trail_id for r in rep.imported] == ["day-2001"]
    assert rep.removed == []
    assert len(rep.failed) == 1 and rep.failed[0][0] == 2003
    assert "ForeignKeyViolation" in rep.failed[0][1]
    assert [r[0] for r in _day_hikes(conn)] == ["day-2001", "day-2003"]  # trail stays
    # The savepoint rolled back, so the Commons photo is not lost either.
    assert (
        conn.execute("select count(*) from photos where trail_id = 'day-2003'").fetchone()[0] == 2
    )


def test_graph_connected_but_not_greedy_chainable_relation_still_has_gaps():
    # Way 12 ends in the middle of way 11 (T-junction without shared end vertex): the graph
    # fallback could walk it, but day hikes stay on greedy chaining (opt-in only for trails).
    ways = [
        _way(11, [(48.07, 8.0), (48.07, 8.02), (48.07, 8.04)]),
        _way(12, [(48.07, 8.02), (48.075, 8.02)]),
    ]
    cands, _ = _scan_all([_rel(3040, {"name": "T-Weg", "network": "lwn"}, ways)])
    assert cands[3040].auto_reason == "Lücken im Verlauf"
