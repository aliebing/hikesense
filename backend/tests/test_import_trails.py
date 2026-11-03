import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from conftest import Ramp

from hikesense.adapters.http import make_http_client
from hikesense.adapters.overpass import OVERPASS_URL, OverpassClient
from hikesense.errors import GapError
from hikesense.ingest.trails import (
    chain_lines,
    import_trail,
    relation_segments,
    trail_line,
    trail_query,
)
from hikesense.models import Source, StageSpec, TrailSpec

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


def _gap_data() -> dict:
    """Parent 2001 has a ~1.5 km gap (8.02-8.04) that only its child relation 2002 closes."""

    def way(ref, pts):
        return {
            "type": "way",
            "ref": ref,
            "role": "",
            "geometry": [{"lat": a, "lon": b} for a, b in pts],
        }

    return {
        "elements": [
            {
                "type": "relation",
                "id": 2001,
                "members": [
                    way(31, [(48.0, 8.0), (48.0, 8.01), (48.0, 8.02)]),
                    {"type": "relation", "ref": 2002, "role": ""},
                    way(32, [(48.0, 8.06), (48.0, 8.05), (48.0, 8.04)]),
                ],
            },
            {
                "type": "relation",
                "id": 2002,
                "members": [way(33, [(48.0, 8.02), (48.0, 8.03), (48.0, 8.04)])],
            },
        ]
    }


def test_relation_group_is_assembled_as_one_piece(small_spec):
    grouped = small_spec.model_copy(update={"osm_relation_ids": [[2001, 2002]]})
    line, warnings = trail_line(grouped, _gap_data())
    assert sorted([line[0], line[-1]]) == [(48.0, 8.0), (48.0, 8.06)]
    assert len(line) == 7 and warnings == []
    assert grouped.relation_ids == [2001, 2002]
    assert "relation(id:2001,2002)" in trail_query(grouped)


def test_single_entry_line_runs_from_the_first_stage_start(small_spec):
    stages = [StageSpec(seq=1, start_name="O", end_name="W", start=(48.0, 8.06), end=(48.0, 8.0))]
    spec = small_spec.model_copy(update={"osm_relation_ids": [[2001, 2002]], "stages": stages})
    line, _ = trail_line(spec, _gap_data())
    assert line[0] == (48.0, 8.06) and line[-1] == (48.0, 8.0)
    spec.stages[0] = StageSpec(
        seq=1, start_name="W", end_name="O", start=(48.0, 8.0), end=(48.0, 8.06)
    )
    line, _ = trail_line(spec, _gap_data())
    assert line[0] == (48.0, 8.0)


def test_without_group_the_parent_gap_still_raises(small_spec):
    plain = small_spec.model_copy(update={"osm_relation_ids": [2001, 2002]})
    with pytest.raises(GapError):
        trail_line(plain, _gap_data())


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
def test_import_records_the_elevation_source(conn, small_spec, overpass_fixture):
    import_trail(conn, small_spec, overpass_fixture, Ramp())
    row = conn.execute("select name, license from sources where id = 'copernicus-glo30'").fetchone()
    assert row and "Copernicus" in row[0] and "DLR" in row[1]


@pytest.mark.db
def test_cli_reports_gap_with_trail_and_relation_and_exits_1(conn, monkeypatch, capsys):
    from hikesense import cli

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


@pytest.mark.parametrize(
    "tid,start,end",
    [
        ("mittelweg", "Pforzheim", "Waldshut"),
        ("ostweg", "Pforzheim", "Schaffhausen"),
    ],
)
def test_curated_trail_chains_its_stages(tid, start, end):
    from hikesense.cli import TRAILS_YAML
    from hikesense.ingest.stages import load_trail_specs

    spec = {t.id: t for t in load_trail_specs(TRAILS_YAML)}[tid]
    assert spec.kind == "long_distance"
    assert spec.stages[0].start_name == start and spec.stages[-1].end_name == end
    for a, b in zip(spec.stages, spec.stages[1:], strict=False):
        assert (a.end_name, a.end) == (b.start_name, b.start) and b.seq == a.seq + 1
    assert all(s.official_km for s in spec.stages)


@pytest.mark.parametrize(
    "tid,stages,first,last",
    [
        ("pfaelzer-weinsteig", 11, "Bockenheim", "Schweigen-Rechtenbach"),
        ("pfaelzer-waldpfad", 8, "Schopp", "Schweigen-Rechtenbach"),
        ("jubilaeumsweg-bodenseekreis", 6, "Kressbronn", "Überlingen"),
        ("seegang", 4, "Konstanz", "Überlingen"),
    ],
)
def test_curated_stage1_trails_have_official_km(tid, stages, first, last):
    from hikesense.cli import TRAILS_YAML
    from hikesense.ingest.stages import load_trail_specs

    spec = {t.id: t for t in load_trail_specs(TRAILS_YAML)}[tid]
    assert len(spec.stages) == stages
    assert spec.stages[0].start_name == first and spec.stages[-1].end_name == last
    for a, b in zip(spec.stages, spec.stages[1:], strict=False):
        assert (a.end_name, a.end) == (b.start_name, b.start) and b.seq == a.seq + 1
    assert all(s.official_km for s in spec.stages)


def test_trim_to_stages_drops_line_before_first_and_after_last_stage():
    from hikesense.ingest.stages import trim_to_stages

    line = [(48.0 + i * 0.01, 8.0) for i in range(10)]
    specs = [
        StageSpec(seq=1, start_name="A", end_name="B", start=line[3], end=line[5]),
        StageSpec(seq=2, start_name="B", end_name="C", start=line[5], end=line[7]),
    ]
    assert trim_to_stages(line, specs) == line[3:8]


def test_trim_to_stages_without_stages_returns_the_line_unchanged():
    from hikesense.ingest.stages import trim_to_stages

    line = [(48.0, 8.0), (48.0, 8.01)]
    assert trim_to_stages(line, []) == line


def test_curated_graph_trails_are_flagged():
    from hikesense.cli import TRAILS_YAML
    from hikesense.ingest.stages import load_trail_specs

    flags = {t.id: t.assemble for t in load_trail_specs(TRAILS_YAML)}
    assert flags["pfaelzer-waldpfad"] == flags["pfaelzer-weinsteig"] == "graph"
    assert flags["mittelweg"] == flags["seegang"] == "greedy"


@pytest.mark.db
def test_import_trail_trims_only_when_spec_asks(conn, small_spec, overpass_fixture):
    inner = [
        StageSpec(seq=1, start_name="A", end_name="B", start=(48.0, 8.01), end=(48.0, 8.03)),
    ]
    plain = small_spec.model_copy(update={"stages": inner})
    assert plain.trim is False
    import_trail(conn, plain, overpass_fixture, Ramp())
    full = conn.execute("select length_km from trails where id=%s", [plain.id]).fetchone()[0]
    import_trail(conn, plain.model_copy(update={"trim": True}), overpass_fixture, Ramp())
    cut = conn.execute("select length_km from trails where id=%s", [plain.id]).fetchone()[0]
    assert cut < full  # the untrimmed import kept the line outside the stages


def test_curated_trim_flag_only_on_new_trails():
    from hikesense.cli import TRAILS_YAML
    from hikesense.ingest.stages import load_trail_specs

    trimmed = {t.id for t in load_trail_specs(TRAILS_YAML) if t.trim}
    assert trimmed == {
        "pfaelzer-weinsteig",
        "pfaelzer-waldpfad",
        "jubilaeumsweg-bodenseekreis",
        "seegang",
    }
