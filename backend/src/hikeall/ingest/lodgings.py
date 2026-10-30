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
        with pieces as (  -- short pieces keep bbox and geography checks cheap on long trails
          select id, st_subdivide(geom, 64) as geom from trails
        ), near as (
          select s.id as trail_id, l.id as lodging_id,
                 min(st_distance(s.geom::geography, l.geom::geography)) as dist
          from pieces s
          join lodgings l on l.geom && st_expand(s.geom, 0.03)  -- index prefilter, > 2 km
            and st_dwithin(s.geom::geography, l.geom::geography, %s)
          group by s.id, l.id
        )
        insert into trail_lodgings (trail_id, lodging_id, dist_m, along_km)
        select n.trail_id, n.lodging_id, round(n.dist)::int,
               (st_linelocatepoint(t.geom, l.geom) * t.length_km)::numeric(8, 3)
        from near n
        join trails t on t.id = n.trail_id
        join lodgings l on l.id = n.lodging_id
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
