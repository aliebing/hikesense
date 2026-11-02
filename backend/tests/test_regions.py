import psycopg
import pytest

from hikeall.errors import OutsideRegionError
from hikeall.ingest.trails import check_in_region
from hikeall.models import BLACK_FOREST_BBOX
from hikeall.regions import REGIONS, get_region, region_of_line


def test_palatinate_bbox():
    assert get_region("palatinate").bbox.south == 48.95
    assert get_region("palatinate").foreign == ("FR",)


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


def test_check_in_region():
    assert check_in_region([(49.3, 8.0), (49.4, 8.1)], "x").id == "palatinate"
    with pytest.raises(OutsideRegionError, match="liegt in keiner Region vollständig"):
        check_in_region([(48.0, 8.0), (49.3, 7.9)], "x")


def test_trails_region_column(conn):
    rows = conn.execute("select distinct region from trails").fetchall()
    assert all(r[0] == "black_forest" for r in rows)
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("update trails set region = 'mars' where id = (select id from trails limit 1)")
