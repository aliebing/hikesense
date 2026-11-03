import psycopg
import pytest

from hikesense.errors import OutsideRegionError
from hikesense.ingest.trails import check_in_region
from hikesense.models import BLACK_FOREST_BBOX
from hikesense.regions import REGIONS, get_region, region_of_line


def test_palatinate_bbox():
    assert get_region("palatinate").bbox.south == 48.95
    assert [(k, v) for k, v, _ in get_region("palatinate").exclude] == [
        ("ISO3166-1", "FR"),
        ("ISO3166-2", "DE-BW"),
        ("ISO3166-2", "DE-HE"),
    ]


def test_lake_constance_closes_gap_to_black_forest():
    assert get_region("lake_constance").bbox.west == get_region("black_forest").bbox.east == 8.80
    assert region_of_line([(47.76, 8.82)]).id == "lake_constance"  # Hohentwiel / Singen


def test_unknown_region_raises():
    with pytest.raises(KeyError):
        get_region("nowhere")


def test_black_forest_alias():
    assert get_region("black_forest").bbox == BLACK_FOREST_BBOX
    assert [r.id for r in REGIONS] == ["black_forest", "palatinate", "lake_constance"]


def test_region_of_line():
    assert region_of_line([(48.0, 8.0), (48.1, 8.1)]).id == "black_forest"
    assert region_of_line([(47.66, 8.86)]).id == "lake_constance"  # Stein am Rhein
    assert region_of_line([(48.0, 8.0), (49.3, 7.9)]) is None
    assert region_of_line([]) is None


def test_check_in_region():
    assert check_in_region([(49.3, 8.0), (49.4, 8.1)], "x").id == "palatinate"
    with pytest.raises(OutsideRegionError, match="liegt in keiner Region vollständig"):
        check_in_region([(48.0, 8.0), (49.3, 7.9)], "x")


@pytest.mark.db
def test_trails_region_column(conn):
    rows = conn.execute("select distinct region from trails").fetchall()
    assert {r[0] for r in rows} <= {"black_forest", "palatinate", "lake_constance"}
    old = conn.execute(
        "select distinct region from trails where id in "
        "('westweg-west', 'westweg-ost', 'mittelweg', 'ostweg')"
    ).fetchall()
    assert old == [("black_forest",)]
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("update trails set region = 'mars' where id = (select id from trails limit 1)")
