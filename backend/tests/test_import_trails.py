import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from conftest import Ramp

from hikeall.adapters.http import make_http_client
from hikeall.adapters.overpass import OVERPASS_URL, OverpassClient
from hikeall.errors import GapError
from hikeall.ingest.trails import (
    chain_lines,
    import_trail,
    relation_segments,
    trail_line,
    trail_query,
)
from hikeall.models import Source, StageSpec, TrailSpec

FIXTURE = Path(__file__).parent / "fixtures" / "overpass_relation_small.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _source(sid: str) -> Source:
    return Source(
        id=sid,
        name=sid,
        url=f"https://example.org/{sid}",
        license="test",
        retrieved_at=date(2026, 10, 28),
    )


@pytest.fixture
def small_spec() -> TrailSpec:
    return TrailSpec(
        id="test-small",
        name="Testweg",
        kind="long_distance",
        osm_relation_ids=[1001, 1002],
        source=_source("test-stages"),
        geometry_source=_source("test-osm"),
        stages=[
            StageSpec(seq=1, start_name="A", end_name="B", start=(48.0, 8.0), end=(48.0, 8.04)),
            StageSpec(seq=2, start_name="B", end_name="C", start=(48.0, 8.04), end=(48.0, 8.08)),
        ],
    )


@pytest.fixture
def overpass_fixture():
    with respx.mock:
        respx.post(OVERPASS_URL).mock(return_value=httpx.Response(200, json=_fixture()))
        with make_http_client(5) as http:
            yield OverpassClient(http, backoff_s=0)


def test_relation_segments_reads_way_geometry_per_relation():
    segs = relation_segments(_fixture(), relation_id=1001)
    assert segs == [
        [(48.0, 8.000), (48.0, 8.010), (48.0, 8.020)],
        [(48.0, 8.040), (48.0, 8.030), (48.0, 8.020)],
    ]


def test_relation_segments_skips_side_roles_nodes_and_subrelations():
    pts = [p for s in relation_segments(_fixture()) for p in s]
    assert pts and all(p[0] == 48.0 for p in pts)  # alternative (48.1) / excursion (47.9) dropped
    assert len(relation_segments(_fixture(), relation_id=1002)) == 2


def test_relation_segments_unknown_relation_raises():
    with pytest.raises(ValueError, match="4711"):
        relation_segments(_fixture(), relation_id=4711)


def test_chain_lines_orients_children_and_checks_gap():
    a = [(48.0, 8.02), (48.0, 8.01), (48.0, 8.00)]  # reversed: must be flipped
    b = [(48.0, 8.02), (48.0, 8.03)]
    assert chain_lines([a, b]) == [(48.0, 8.00), (48.0, 8.01), (48.0, 8.02), (48.0, 8.03)]
    with pytest.raises(GapError):
        chain_lines([a, [(48.0, 8.05), (48.0, 8.06)]])  # ~2.2 km apart


def test_trail_query_asks_for_all_relations_with_geometry(small_spec):
    q = trail_query(small_spec)
    assert "relation(id:1001,1002)" in q and "out geom" in q


@pytest.mark.db
def test_import_trail_writes_trail_and_stages(conn, small_spec, overpass_fixture):
    rep = import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert rep.stages == len(small_spec.stages)
    row = conn.execute(
        "select length_km, source_id from trails where id=%s", [small_spec.id]
    ).fetchone()
    assert row[0] > 0 and row[1]


@pytest.mark.db
def test_reimport_is_idempotent(conn, small_spec, overpass_fixture):
    import_trail(conn, small_spec, overpass_fixture, Ramp())
    import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert conn.execute(
        "select count(*) from stages where trail_id=%s", [small_spec.id]
    ).fetchone()[0] == len(small_spec.stages)


@pytest.mark.db
def test_import_stores_sources_geometry_and_stage_ids(conn, small_spec, overpass_fixture):
    rep = import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert rep.length_km == pytest.approx(5.96, abs=0.05)  # 0.08° lon at 48° N
    trail = conn.execute(
        "select source_id, st_npoints(geom), ascent_m, jsonb_array_length(profile) "
        "from trails where id=%s",
        [small_spec.id],
    ).fetchone()
    assert trail[0] == "test-osm" and trail[1] == 9 and trail[2] > 0 and trail[3] > 2
    stages = conn.execute(
        "select id, source_id, name, round(length_km, 1) from stages where trail_id=%s order by seq",
        [small_spec.id],
    ).fetchall()
    assert [s[0] for s in stages] == ["test-small-01", "test-small-02"]
    assert {s[1] for s in stages} == {"test-stages"}
    assert stages[0][2] == "A – B"
    assert [float(s[3]) for s in stages] == [3.0, 3.0]


@pytest.mark.db
def test_cli_reports_gap_with_trail_and_relation_and_exits_1(conn, monkeypatch, capsys):
    from hikeall import cli

    def boom(*_args):
        raise GapError(11700, (48.88, 8.70), "westweg-west: relation 48073")

    monkeypatch.setenv("SUPABASE_DB_URL", conn.info.dsn + " password=postgres")
    monkeypatch.setattr(cli, "import_trail", boom)
    assert cli.main(["import-trails", "--only", "westweg-west"]) == 1
    err = capsys.readouterr().err
    assert "westweg-west" in err and "relation 48073" in err and "GapError" in err


@pytest.mark.db
def test_stage_deviating_over_5_percent_from_official_km_is_warned(
    conn, small_spec, overpass_fixture
):
    small_spec.stages[0].official_km = 2.0  # line gives ~3.0 km
    small_spec.stages[1].official_km = 3.05  # within 5 %
    rep = import_trail(conn, small_spec, overpass_fixture, Ramp())
    assert len(rep.warnings) == 1 and "Etappe 1" in rep.warnings[0]


def test_dropped_leftovers_become_warnings(small_spec):
    data = _fixture()
    ring = [(48.0003, 8.015), (48.0004, 8.015), (48.0004, 8.0151), (48.0003, 8.015)]
    data["elements"][0]["members"].append(
        {"type": "way", "ref": 14, "role": "", "geometry": [{"lat": a, "lon": b} for a, b in ring]}
    )
    line, warnings = trail_line(small_spec, data)
    assert len(line) == 9
    assert len(warnings) == 1 and "Relation 1001" in warnings[0] and "1 Teilstück" in warnings[0]
