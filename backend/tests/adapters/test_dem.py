import httpx
import numpy as np
import pytest
import respx
import tifffile

from hikeall.adapters.dem import TILE_BASE_URL, CopernicusDem, tile_name
from hikeall.errors import ElevationUnavailable
from hikeall.models import LatLon

# 3 × 3 pixels, 0.5° apart: pixel centres at lat 48.0/47.5/47.0 and lon 8.0/8.5/9.0.
VALUES = [[0, 10, 20], [100, 110, 120], [200, 210, 220]]


def _write(path, north, west, values=VALUES, step=0.5):
    tifffile.imwrite(path, np.asarray(values, dtype=np.float32), extratags=[
        (33550, "d", 3, (step, step, 0.0)), (33922, "d", 6, (0.0, 0.0, 0.0, west, north, 0.0))])


def test_tile_names_follow_the_copernicus_scheme():
    assert tile_name(47, 8) == "Copernicus_DSM_COG_10_N47_00_E008_00_DEM"
    assert tile_name(49, 7) == "Copernicus_DSM_COG_10_N49_00_E007_00_DEM"


def test_bilinear_interpolation_from_a_cached_tile(tmp_path):
    _write(tmp_path / f"{tile_name(47, 8)}.tif", north=48.0, west=8.0)
    dem = CopernicusDem(http=None, cache_dir=tmp_path)
    assert dem.elevations([LatLon(lat=48.0, lon=8.0)]) == [None]  # lat 48.0 belongs to tile N48 (absent)
    assert dem.elevations([LatLon(lat=47.75, lon=8.25)]) == [pytest.approx(55.0)]
    assert dem.elevations([LatLon(lat=47.5, lon=8.5)]) == [pytest.approx(110.0)]


def test_points_on_tile_edges_use_the_right_tile_and_stay_in_the_raster(tmp_path):
    _write(tmp_path / f"{tile_name(47, 8)}.tif", north=48.0, west=8.0)
    _write(tmp_path / f"{tile_name(48, 8)}.tif", north=49.0, west=8.0, values=[[1, 1, 1], [2, 2, 2], [3, 3, 3]])
    dem = CopernicusDem(http=None, cache_dir=tmp_path)
    # lat exactly 48.0 → tile N48, its southern row; lat 47.0 → tile N47, its southern row
    assert dem.elevations([LatLon(lat=48.0, lon=8.25), LatLon(lat=47.0, lon=8.0)]) == [
        pytest.approx(3.0), pytest.approx(200.0)]


@respx.mock
def test_missing_tiles_are_downloaded_once_and_sea_tiles_give_none(tmp_path):
    src = tmp_path / "src.tif"
    _write(src, north=48.0, west=8.0)
    name = tile_name(47, 8)
    got = respx.get(f"{TILE_BASE_URL}{name}/{name}.tif").mock(return_value=httpx.Response(200, content=src.read_bytes()))
    sea = tile_name(47, 9)
    none = respx.get(f"{TILE_BASE_URL}{sea}/{sea}.tif").mock(return_value=httpx.Response(404))
    cache = tmp_path / "dem"
    with httpx.Client() as http:
        dem = CopernicusDem(http=http, cache_dir=cache)
        assert dem.elevations([LatLon(lat=47.5, lon=8.5), LatLon(lat=47.5, lon=9.5)]) == [pytest.approx(110.0), None]
        CopernicusDem(http=http, cache_dir=cache).elevations([LatLon(lat=47.5, lon=9.5)])
    assert got.call_count == 1 and none.call_count == 1  # the 404 is remembered on disk
    assert (cache / f"{name}.tif").exists()


@respx.mock
def test_server_errors_raise_elevation_unavailable(tmp_path):
    name = tile_name(47, 8)
    respx.get(f"{TILE_BASE_URL}{name}/{name}.tif").mock(return_value=httpx.Response(503))
    with httpx.Client() as http, pytest.raises(ElevationUnavailable):
        CopernicusDem(http=http, cache_dir=tmp_path).elevations([LatLon(lat=47.5, lon=8.5)])


def test_only_max_tiles_stay_in_memory(tmp_path):
    for lat in (46, 47, 48):
        _write(tmp_path / f"{tile_name(lat, 8)}.tif", north=lat + 1.0, west=8.0)
    dem = CopernicusDem(http=None, cache_dir=tmp_path, max_tiles=2)
    dem.elevations([LatLon(lat=46.5, lon=8.5), LatLon(lat=47.5, lon=8.5), LatLon(lat=48.5, lon=8.5)])
    assert len(dem._tiles) == 2


def test_an_unreadable_tile_raises_elevation_unavailable_and_is_removed(tmp_path):
    path = tmp_path / f"{tile_name(47, 8)}.tif"
    path.write_bytes(b"<html>captive portal</html>")
    with pytest.raises(ElevationUnavailable, match="unreadable"):
        CopernicusDem(http=None, cache_dir=tmp_path).elevations([LatLon(lat=47.5, lon=8.5)])
    assert not path.exists()  # downloaded again on the next run
