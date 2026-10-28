"""Lodgings from OSM (ODbL): fetch within the import bbox, upsert, link to trails (<= 2 km)."""

from __future__ import annotations

import time
from typing import Any

import psycopg

from hikeall.adapters.overpass import OverpassClient
from hikeall.db import upsert_lodging, upsert_source
from hikeall.ingest.day_hikes import tiles
from hikeall.models import BBox, Lodging, Source

TOURISM_KINDS = (
    "hotel",
    "guest_house",
    "hostel",
    "alpine_hut",
    "wilderness_hut",
    "chalet",
    "apartment",
    "camp_site",
)
BUFFER_M = 2000


def lodgings_query(bbox: BBox) -> str:
    """One exact-match clause per kind and element type (regex filters are far slower)."""
    b = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
    parts = "".join(
        f'{el}["tourism"="{k}"]["name"]({b});' for k in TOURISM_KINDS for el in ("node", "way")
    )
    return f"[out:json][timeout:240];({parts});out center;"


def parse_lodgings(data: dict[str, Any]) -> list[Lodging]:
    """Nodes and ways (`out center`); way ids negative; unnamed or other kinds dropped."""
    out: list[Lodging] = []
    for el in data["elements"]:
        tags = el.get("tags") or {}
        kind = tags.get("tourism")
        name = (tags.get("name") or "").strip()
        if kind not in TOURISM_KINDS or not name:
            continue
        if el["type"] == "node":
            pos = el
        elif el["type"] == "way":
            pos = el.get("center")
        else:
            continue
        if not pos or "lat" not in pos or "lon" not in pos:
            continue
        sign = -1 if el["type"] == "way" else 1
        out.append(
            Lodging(
                id=sign * int(el["id"]),
                name=name,
                kind=kind,
                website=tags.get("website") or tags.get("contact:website") or None,
                lat=pos["lat"],
                lon=pos["lon"],
            )
        )
    return out


def fetch_lodgings(
    overpass: OverpassClient, bbox: BBox, step_deg: float = 0.35, pause_s: float = 2.0
) -> list[Lodging]:
    """Tile by tile (small queries), deduplicated by id.

    Raises OverpassError after the adapter's retries, so nothing is half imported."""
    found: dict[int, Lodging] = {}
    for i, tile in enumerate(tiles(bbox, step_deg)):
        if i and pause_s:
            time.sleep(pause_s)
        for lodging in parse_lodgings(overpass.run(lodgings_query(tile))):
            found[lodging.id] = lodging
    return list(found.values())


def link_trail_lodgings(conn: psycopg.Connection) -> int:
    """Rebuild trail_lodgings: every pair within 2 km; returns the row count."""
    conn.execute("delete from trail_lodgings")
    cur = conn.execute(
        """
        insert into trail_lodgings (trail_id, lodging_id, dist_m, along_km)
        select t.id, l.id,
               round(st_distance(t.geom::geography, l.geom::geography))::int,
               (st_linelocatepoint(t.geom, l.geom) * t.length_km)::numeric(8, 3)
        from trails t
        join lodgings l on st_dwithin(t.geom::geography, l.geom::geography, %s)
        """,
        [BUFFER_M],
    )
    return cur.rowcount


def import_lodgings(conn: psycopg.Connection, lodgings: list[Lodging], source: Source) -> int:
    """Upsert, link, drop lodgings farther than 2 km from every trail. Returns links."""
    upsert_source(conn, source)
    for lodging in lodgings:
        upsert_lodging(conn, lodging, source.id)
    n = link_trail_lodgings(conn)
    conn.execute(
        "delete from lodgings where source_id = %s"
        " and id not in (select lodging_id from trail_lodgings)",
        [source.id],
    )
    return n
