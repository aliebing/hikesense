from pathlib import Path

import pytest
from conftest import LINE

from hikesense.errors import HikeSenseError, StageOffsetError, StageOrderError
from hikesense.ingest.stages import cut_stages, load_trail_specs
from hikesense.models import StageSpec

TRAILS_YAML = Path(__file__).resolve().parents[2] / "data" / "curated" / "trails.yaml"


def test_cut_stages_splits_at_nearest_points():
    specs = [
        StageSpec(seq=1, start_name="A", end_name="B", start=(48.0, 8.0), end=(48.0, 8.05)),
        StageSpec(seq=2, start_name="B", end_name="C", start=(48.0, 8.05), end=(48.0, 8.1)),
    ]
    parts = cut_stages(LINE, specs)
    assert len(parts) == 2
    assert parts[0][-1] == parts[1][0]
    assert parts[0][-1] == pytest.approx((48.0, 8.05), abs=1e-5)  # <= ~1 m


def test_stage_endpoint_far_from_line_raises():
    specs = [
        StageSpec(seq=1, start_name="A", end_name="Irgendwo", start=(48.0, 8.0), end=(48.1, 8.05))
    ]
    with pytest.raises(StageOffsetError, match="Irgendwo"):
        cut_stages(LINE, specs)


def test_stage_offset_error_is_hikesense_error():
    assert issubclass(StageOffsetError, HikeSenseError)


def test_trails_yaml_is_complete():
    specs = load_trail_specs(TRAILS_YAML)
    ids = {t.id for t in specs}
    assert {"westweg-west", "westweg-ost"} <= ids
    for t in specs:
        assert t.osm_relation_ids and t.source.url and t.stages
        assert [s.seq for s in t.stages] == list(range(1, len(t.stages) + 1))


def test_stage_start_far_from_line_raises():
    specs = [
        StageSpec(seq=1, start_name="Nirgendwo", end_name="B", start=(48.1, 8.0), end=(48.0, 8.05))
    ]
    with pytest.raises(StageOffsetError, match="Nirgendwo"):
        cut_stages(LINE, specs)


def test_reversed_stage_raises_naming_stage():
    specs = [
        StageSpec(seq=3, start_name="B", end_name="Zurueck", start=(48.0, 8.05), end=(48.0, 8.0))
    ]
    with pytest.raises(StageOrderError, match="Zurueck") as exc:
        cut_stages(LINE, specs)
    assert exc.value.seq == 3


def test_one_point_stage_raises():
    specs = [StageSpec(seq=1, start_name="A", end_name="A2", start=(48.0, 8.05), end=(48.0, 8.05))]
    with pytest.raises(StageOrderError, match="A2"):
        cut_stages(LINE, specs)


def test_stage_starting_before_previous_end_raises():
    specs = [
        StageSpec(seq=1, start_name="A", end_name="B", start=(48.0, 8.0), end=(48.0, 8.05)),
        StageSpec(seq=2, start_name="Frueher", end_name="C", start=(48.0, 8.02), end=(48.0, 8.1)),
    ]
    with pytest.raises(StageOrderError, match="Frueher"):
        cut_stages(LINE, specs)


def test_out_and_back_second_stage_snaps_to_second_pass():
    out = LINE[:51]  # 8.000 .. 8.050
    line = out + LINE[49::-1]  # back 8.049 .. 8.000; 8.02 occurs at idx 20 and idx 80
    specs = [
        StageSpec(seq=1, start_name="A", end_name="Turn", start=(48.0, 8.0), end=(48.0, 8.05)),
        StageSpec(seq=2, start_name="Turn", end_name="Back", start=(48.0, 8.05), end=(48.0, 8.02)),
    ]
    parts = cut_stages(line, specs)
    assert len(parts[0]) == 51
    assert len(parts[1]) == 31  # idx 50..80, not a wrong snap to the first pass
    assert parts[1][-1] == pytest.approx((48.0, 8.02), abs=1e-5)


def test_trails_yaml_names_both_sources():
    for t in load_trail_specs(TRAILS_YAML):
        assert t.geometry_source.id == "osm" and t.geometry_source.license == "ODbL"
        assert t.source.id != t.geometry_source.id


def test_unknown_source_id_is_a_clear_error(tmp_path):
    bad = tmp_path / "trails.yaml"
    bad.write_text(
        "sources: []\ntrails:\n  - {id: x, name: X, kind: long_distance, osm_relation_ids: [1],"
        " source: nope, geometry_source: nope, stages: []}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'nope' is not listed under sources"):
        load_trail_specs(bad)
