"""Places and points of interest from OSM (ODbL): fetch within the import bbox, upsert, and
link POIs to trails (<= 300 m)."""

from __future__ import annotations

import time
from typing import Any

import psycopg

from hikeall.adapters.overpass import OverpassClient
from hikeall.db import upsert_place, upsert_poi, upsert_source
from hikeall.ingest.day_hikes import tiles
from hikeall.models import BBox, Place, Poi, Source

POI_BUFFER_M = 300
RELATION_ID_OFFSET = 10**12  # relation ids live far below any way id (see _position)
PLACE_KINDS = ("city", "town", "village", "hamlet")  # OSM place= values we fetch
STORED_KIND = {"city": "town"}  # a city is a town for tags/ranking (no new kind, no migration)
MUNICIPALITY_ADMIN_LEVEL = "8"  # Gemeinde
FOOD_AMENITIES = ("restaurant", "cafe", "biergarten", "pub")

# (tag, value, requires name) -> POI kind; first match wins for multi-tagged elements.
POI_RULES: tuple[tuple[str, str, bool, str], ...] = (
    ("tourism", "viewpoint", False, "viewpoint"),
    ("natural", "peak", True, "peak"),
    ("waterway", "waterfall", False, "waterfall"),
    *(("amenity", a, False, "food") for a in FOOD_AMENITIES),
    ("tourism", "alpine_hut", False, "hut"),
    ("railway", "station", False, "station"),
    ("railway", "halt", False, "station"),
)


def _bbox(b: BBox) -> str:
    return f"{b.south},{b.west},{b.north},{b.east}"


def places_query(bbox: BBox) -> str:
    """Exact-match clauses (regex filters are far slower); ways/areas via `out center`."""
    b = _bbox(bbox)
    parts = "".join(f'node["place"="{k}"]["name"]({b});' for k in PLACE_KINDS)
    parts += f'node["natural"="peak"]["name"]({b});'
    for el in ("way", "relation"):
        parts += f'{el}["natural"="water"]["water"="lake"]["name"]({b});'
    parts += f'relation["boundary"="administrative"]["admin_level"="8"]["name"]({b});'
    return f"[out:json][timeout:240];({parts});out center;"


def pois_query(bbox: BBox) -> str:
    b = _bbox(bbox)
    parts = ""
    for tag, value, _named, _kind in POI_RULES:
        for el in ("node", "way"):
            if (tag, value) == ("natural", "peak") and el == "way":
                continue
            parts += f'{el}["{tag}"="{value}"]({b});'
    parts += f'node["amenity"="shelter"]["shelter_type"="basic_hut"]({b});'
    parts += f'way["amenity"="shelter"]["shelter_type"="basic_hut"]({b});'
    return f"[out:json][timeout:240];({parts});out center;"


def _position(el: dict[str, Any]) -> tuple[int, float, float] | None:
    """(id, lat, lon) via `out center`; centerless elements: None.

    Id scheme (one bigint space, no collisions): nodes +id, ways -id,
    relations -(10**12 + id) (OSM way ids stay far below 10**12)."""
    if el["type"] == "node":
        pos, oid = el, int(el["id"])
    elif el["type"] == "way":
        pos, oid = el.get("center"), -int(el["id"])
    elif el["type"] == "relation":
        pos, oid = el.get("center"), -(RELATION_ID_OFFSET + int(el["id"]))
    else:
        return None
    if not pos or "lat" not in pos or "lon" not in pos:
        return None
    return oid, pos["lat"], pos["lon"]


def _poi_kind(tags: dict[str, str]) -> str | None:
    for tag, value, needs_name, kind in POI_RULES:
        if tags.get(tag) == value and (not needs_name or (tags.get("name") or "").strip()):
            return kind
    if tags.get("amenity") == "shelter" and tags.get("shelter_type") == "basic_hut":
        return "hut"
    return None


def parse_pois(data: dict[str, Any]) -> list[Poi]:
    out: list[Poi] = []
    for el in data["elements"]:
        tags = el.get("tags") or {}
        kind = _poi_kind(tags)
        pos = _position(el)
        if kind is None or pos is None:
            continue
        out.append(
            Poi(
                id=pos[0],
                name=(tags.get("name") or "").strip() or None,
                kind=kind,
                lat=pos[1],
                lon=pos[2],
            )
        )
    return out


def parse_places(data: dict[str, Any]) -> list[Place]:
    """Named towns/villages/hamlets, peaks, lakes and municipalities (center); unnamed ones are dropped."""
    out: list[Place] = []
    for el in data["elements"]:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if tags.get("place") in PLACE_KINDS:
            kind = STORED_KIND.get(tags["place"], tags["place"])
        elif tags.get("natural") == "peak":
            kind = "peak"
        elif tags.get("natural") == "water" and tags.get("water") == "lake":
            kind = "lake"
        elif (
            el["type"] == "relation"
            and tags.get("boundary") == "administrative"
            and tags.get("admin_level") == MUNICIPALITY_ADMIN_LEVEL
        ):
            kind = "municipality"
        else:
            continue
        pos = _position(el)
        if not name or pos is None:
            continue
        out.append(Place(id=pos[0], name=name, kind=kind, lat=pos[1], lon=pos[2]))
    return out


def _fetch_tiled(overpass, bbox, query, parse, step_deg, pause_s):
    found: dict[int, Any] = {}
    for i, tile in enumerate(tiles(bbox, step_deg)):
        if i and pause_s:
            time.sleep(pause_s)
        for item in parse(overpass.run(query(tile))):
            found[item.id] = item
    return list(found.values())


def fetch_places(
    overpass: OverpassClient, bbox: BBox, step_deg: float = 0.35, pause_s: float = 2.0
) -> list[Place]:
    """Tile by tile, deduplicated; raises OverpassError, so nothing is half imported."""
    return _fetch_tiled(overpass, bbox, places_query, parse_places, step_deg, pause_s)


def fetch_pois(
    overpass: OverpassClient, bbox: BBox, step_deg: float = 0.2, pause_s: float = 2.0
) -> list[Poi]:
    return _fetch_tiled(overpass, bbox, pois_query, parse_pois, step_deg, pause_s)


def link_trail_pois(conn: psycopg.Connection) -> int:
    """Rebuild trail_pois: every pair within 300 m; returns the row count."""
    conn.execute("delete from trail_pois")
    cur = conn.execute(
        """
        insert into trail_pois (trail_id, poi_id, dist_m, along_km)
        select t.id, p.id,
               round(st_distance(t.geom::geography, p.geom::geography))::int,
               (st_linelocatepoint(t.geom, p.geom) * t.length_km)::numeric(8, 3)
        from trails t
        join pois p on t.geom && st_expand(p.geom, 0.01)  -- index prefilter, > 300 m
          and st_dwithin(t.geom::geography, p.geom::geography, %s)
        """,
        [POI_BUFFER_M],
    )
    return cur.rowcount


def import_places(
    conn: psycopg.Connection, places: list[Place], pois: list[Poi], source: Source
) -> int:
    """Upsert places and POIs, link POIs, drop POIs farther than 300 m from every trail and
    places of this source that are no longer in OSM. Returns trail-POI links."""
    upsert_source(conn, source)
    for place in places:
        upsert_place(conn, place, source.id)
    for poi in pois:
        upsert_poi(conn, poi, source.id)
    n = link_trail_pois(conn)
    conn.execute(
        "delete from pois where source_id = %s and id not in (select poi_id from trail_pois)",
        [source.id],
    )
    if places:  # an empty fetch never wipes the table
        conn.execute(
            "delete from places where source_id = %s and id <> all(%s)",
            [source.id, [p.id for p in places]],
        )
    return n
