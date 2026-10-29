"""Elevation from local Copernicus GLO-30 tiles (spec §18.5): no API limit, read at ingest only.

Tiles are 1° × 1° Cloud-Optimised GeoTIFFs on AWS Open Data, downloaded on first use into
data/dem/. A 404 means there is no land tile (sea) and is remembered with a marker file.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import tifffile

from hikeall.errors import ElevationUnavailable
from hikeall.models import LatLon

TILE_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com/"
_PIXEL_SCALE, _TIEPOINT = 33550, 33922
_NODATA_BELOW = -500.0


def tile_name(lat_deg: int, lon_deg: int) -> str:
    ns, ew = ("N" if lat_deg >= 0 else "S"), ("E" if lon_deg >= 0 else "W")
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_deg):02d}_00_{ew}{abs(lon_deg):03d}_00_DEM"


@dataclass(frozen=True)
class _Tile:
    data: np.ndarray
    west: float
    north: float
    dx: float
    dy: float

    def value(self, lat: float, lon: float) -> float | None:
        rows, cols = self.data.shape
        x = (lon - self.west) / self.dx
        y = (self.north - lat) / self.dy
        c0, r0 = min(max(int(x), 0), cols - 1), min(max(int(y), 0), rows - 1)
        c1, r1 = min(c0 + 1, cols - 1), min(r0 + 1, rows - 1)
        fx, fy = min(max(x - c0, 0.0), 1.0), min(max(y - r0, 0.0), 1.0)
        d = self.data
        v = (d[r0, c0] * (1 - fx) * (1 - fy) + d[r0, c1] * fx * (1 - fy)
             + d[r1, c0] * (1 - fx) * fy + d[r1, c1] * fx * fy)
        v = float(v)
        return v if math.isfinite(v) and v > _NODATA_BELOW else None


class CopernicusDem:
    def __init__(self, http: httpx.Client | None, cache_dir: Path, max_tiles: int = 2,
                 base_url: str = TILE_BASE_URL) -> None:
        self._http = http
        self._dir = cache_dir
        self._max = max_tiles
        self._base = base_url
        self._tiles: OrderedDict[tuple[int, int], _Tile | None] = OrderedDict()

    def elevations(self, points: list[LatLon]) -> list[float | None]:
        result: list[float | None] = []
        for p in points:
            tile = self._tile(math.floor(p.lat), math.floor(p.lon))
            result.append(tile.value(p.lat, p.lon) if tile else None)
        return result

    def _tile(self, lat_deg: int, lon_deg: int) -> _Tile | None:
        key = (lat_deg, lon_deg)
        if key in self._tiles:
            self._tiles.move_to_end(key)
            return self._tiles[key]
        tile = self._load(tile_name(lat_deg, lon_deg))
        self._tiles[key] = tile
        while len(self._tiles) > self._max:
            self._tiles.popitem(last=False)
        return tile

    def _load(self, name: str) -> _Tile | None:
        path, missing = self._dir / f"{name}.tif", self._dir / f"{name}.missing"
        if missing.exists():
            return None
        if not path.exists() and not self._download(name, path, missing):
            return None
        # GLO-30 is PixelIsPoint: the tiepoint is the centre of pixel (0, 0), as _Tile.value assumes.
        try:
            with tifffile.TiffFile(path) as tif:
                page = tif.pages[0]
                dx, dy, _ = page.tags[_PIXEL_SCALE].value
                west, north = page.tags[_TIEPOINT].value[3:5]
                data = page.asarray().astype(np.float32, copy=False)
        except (tifffile.TiffFileError, KeyError, ValueError, OSError) as exc:
            path.unlink(missing_ok=True)  # e.g. an HTML error page saved as .tif: fetch it again next run
            raise ElevationUnavailable(f"DEM tile {name} unreadable ({type(exc).__name__})") from exc
        return _Tile(data, float(west), float(north), float(dx), float(dy))

    def _download(self, name: str, path: Path, missing: Path) -> bool:
        if self._http is None:
            return False
        self._dir.mkdir(parents=True, exist_ok=True)
        url = f"{self._base}{name}/{name}.tif"
        problem = "unknown error"
        for _ in range(2):
            try:
                response = self._http.get(url)
            except httpx.TransportError as exc:
                problem = type(exc).__name__
                continue
            if response.status_code == 404:
                missing.touch()
                return False
            if response.status_code == 200:
                tmp = path.with_suffix(".part")
                tmp.write_bytes(response.content)
                tmp.replace(path)
                return True
            problem = f"HTTP {response.status_code}"
        raise ElevationUnavailable(f"DEM tile {name} failed ({problem})")
