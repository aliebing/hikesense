from pathlib import Path

import pytest
from conftest import LINE

from hikeall.errors import HikeAllError, StageOffsetError
from hikeall.ingest.stages import cut_stages, load_trail_specs
from hikeall.models import StageSpec

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


def test_stage_offset_error_is_hikeall_error():
    assert issubclass(StageOffsetError, HikeAllError)


def test_trails_yaml_is_complete():
    specs = load_trail_specs(TRAILS_YAML)
    ids = {t.id for t in specs}
    assert {"westweg-west", "westweg-ost"} <= ids
    for t in specs:
        assert t.osm_relation_ids and t.source.url and t.stages
        assert [s.seq for s in t.stages] == list(range(1, len(t.stages) + 1))
