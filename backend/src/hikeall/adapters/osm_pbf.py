"""Places/POI elements from a local OSM extract (Geofabrik .osm.pbf, ODbL) in the shape of an
Overpass `out center` response, so ingest.places.parse_places/parse_pois work unchanged."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import osmium
import osmium.filter

from hikeall.ingest.lodgings import TOURISM_KINDS
from hikeall.ingest.places import MUNICIPALITY_ADMIN_LEVEL, PLACE_KINDS, POI_RULES
from hikeall.models import BBox

if TYPE_CHECKING:
    from hikeall.regions import Region

What = Literal["places", "lodgings"]

_POI_TAGS = {(t, v) for t, v, _n, _k in POI_RULES}


def _named(tags) -> bool:
    return bool((tags.get("name") or "").strip())


def _is_lake(tags) -> bool:
    return tags.get("natural") == "water" and tags.get("water") == "lake" and _named(tags)


def _is_municipality(tags) -> bool:
    return (
        tags.get("boundary") == "administrative"
        and tags.get("admin_level") == MUNICIPALITY_ADMIN_LEVEL
        and _named(tags)
    )


def _matches_node(tags) -> bool:
    """Same filters as ingest.places.places_query/pois_query for nodes."""
    if tags.get("place") in PLACE_KINDS and _named(tags):
        return True
    if tags.get("natural") == "peak":
        return _named(tags)
    return _matches_poi(tags)


def _matches_poi(tags) -> bool:
    if any(tags.get(t) == v for t, v in _POI_TAGS):
        return True
    return tags.get("amenity") == "shelter" and tags.get("shelter_type") == "basic_hut"


def _matches_lodging(tags) -> bool:
    """Same filter as ingest.lodgings.lodgings_query (nodes and ways)."""
    return tags.get("tourism") in TOURISM_KINDS and _named(tags)


def _matches_way(tags) -> bool:
    # peaks are node-only; lakes come in through areas
    return tags.get("natural") != "peak" and _matches_poi(tags)


def _ring_centroid(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
    """(signed area, cx, cy) of a closed ring of (x=lon, y=lat); vertex mean if degenerate."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1], strict=True):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-18:
        return 0.0, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    return a / 2, cx / (3 * a), cy / (3 * a)


def _area_center(area) -> tuple[float, float] | None:
    """Centroid of an area: outer rings add, inner rings (holes) subtract."""
    tot = sx = sy = 0.0
    rings = []
    for outer in area.outer_rings():
        rings.append((outer, 1.0))
        rings.extend((inner, -1.0) for inner in area.inner_rings(outer))
    for ring, sign in rings:
        pts = [(n.lon, n.lat) for n in ring if n.location.valid()]
        if len(pts) < 3:
            continue
        a, cx, cy = _ring_centroid(pts)
        w = sign * abs(a)
        tot += w
        sx += w * cx
        sy += w * cy
    return (sy / tot, sx / tot) if tot > 0 else None


def _way_center(nodes) -> tuple[float, float] | None:
    pts = [(n.lon, n.lat) for n in nodes if n.location.valid()]
    if not pts:
        return None
    if len(pts) > 3 and pts[0] == pts[-1]:
        a, cx, cy = _ring_centroid(pts[:-1])
        if a:
            return cy, cx
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def _inside(bbox: BBox, lat: float, lon: float) -> bool:
    return bbox.south <= lat <= bbox.north and bbox.west <= lon <= bbox.east


def pbf_timestamp(path: Path) -> str | None:
    """OSM replication timestamp of the extract (header), if present."""
    with osmium.io.Reader(str(path), osmium.osm.osm_entity_bits.NOTHING) as reader:
        return reader.header().get("osmosis_replication_timestamp") or None


def read_elements(pbf_path: Path, bbox: BBox, what: What = "places") -> dict[str, Any]:
    """One pass over the file; Overpass-shaped elements inside the bbox for the same tag
    filters as places_query/pois_query (`what="places"`) or lodgings_query (`"lodgings"`).
    Ways/relations carry `center` = geometry centroid."""
    lodgings = what == "lodgings"
    elements: list[dict[str, Any]] = []

    def add(kind: str, oid: int, tags, lat: float, lon: float) -> None:
        if not _inside(bbox, lat, lon):
            return
        el: dict[str, Any] = {"type": kind, "id": oid, "tags": dict(tags)}
        if kind == "node":
            el.update(lat=lat, lon=lon)
        else:
            el["center"] = {"lat": lat, "lon": lon}
        elements.append(el)

    with tempfile.TemporaryDirectory() as tmp:
        # disk-backed node index: a flex_mem cache of all nodes of a state is several GB
        index = f"sparse_file_array,{Path(tmp) / 'nodes.idx'}"
        fp = osmium.FileProcessor(str(pbf_path)).with_locations(index)
        if not lodgings:
            fp = fp.with_areas(
                osmium.filter.TagFilter(("natural", "water"), ("boundary", "administrative"))
            )
        for o in fp:
            if not o.tags:
                continue
            if lodgings:
                if o.is_node() and o.location.valid() and _matches_lodging(o.tags):
                    add("node", o.id, o.tags, o.location.lat, o.location.lon)
                elif o.is_way() and _matches_lodging(o.tags) and (c := _way_center(o.nodes)):
                    add("way", o.id, o.tags, *c)
                continue
            if o.is_node():
                if o.location.valid() and _matches_node(o.tags):
                    add("node", o.id, o.tags, o.location.lat, o.location.lon)
            elif o.is_way():
                if _matches_way(o.tags) and (c := _way_center(o.nodes)):
                    add("way", o.id, o.tags, *c)
            elif (
                o.is_area()
                and (_is_lake(o.tags) or (not o.from_way() and _is_municipality(o.tags)))
                and (c := _area_center(o))
            ):
                add("way" if o.from_way() else "relation", o.orig_id(), o.tags, *c)
    return {"elements": elements}


def extract_paths(pbf_dir: Path, region: Region) -> list[Path] | None:
    """The region's Geofabrik extracts in `pbf_dir`, or None if one is missing (or none set)."""
    paths = [pbf_dir / f"{name}-latest.osm.pbf" for name in region.extracts]
    return paths if paths and all(p.is_file() for p in paths) else None


def read_regions(pbf_dir: Path, regions: Sequence[Region], what: What) -> dict[str, dict]:
    """Elements per region id for every region whose extracts are all in `pbf_dir`.

    Each file is read once, with the union of the boxes of the regions that use it; the
    elements are then split by region box (a file can serve several regions)."""
    users: dict[Path, list[Region]] = {}
    out: dict[str, dict] = {}
    for region in regions:
        paths = extract_paths(pbf_dir, region)
        if paths is None:
            continue
        out[region.id] = {"elements": []}
        for path in paths:
            users.setdefault(path, []).append(region)
    for path, rs in users.items():
        union = BBox(
            south=min(r.bbox.south for r in rs),
            west=min(r.bbox.west for r in rs),
            north=max(r.bbox.north for r in rs),
            east=max(r.bbox.east for r in rs),
        )
        for el in read_elements(path, union, what)["elements"]:
            pos = el if el["type"] == "node" else el["center"]
            for r in rs:
                if _inside(r.bbox, pos["lat"], pos["lon"]):
                    out[r.id]["elements"].append(el)
    return out
