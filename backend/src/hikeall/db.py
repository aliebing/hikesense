"""Postgres access helpers."""

from __future__ import annotations

from collections.abc import Sequence

import psycopg
from psycopg.types.json import Jsonb

from hikeall.models import Lodging, Source


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url)


def upsert_source(conn: psycopg.Connection, source: Source) -> None:
    conn.execute(
        """
        insert into sources (id, name, url, license, retrieved_at)
        values (%(id)s, %(name)s, %(url)s, %(license)s, %(retrieved_at)s)
        on conflict (id) do update set
            name = excluded.name,
            url = excluded.url,
            license = excluded.license,
            retrieved_at = excluded.retrieved_at
        """,
        source.model_dump(),
    )


def _wkt(line: Sequence[tuple[float, float]]) -> str:
    """(lat, lon) points → WKT LineString in lon/lat order."""
    return "LINESTRING(" + ",".join(f"{lon} {lat}" for lat, lon in line) + ")"


def upsert_trail(
    conn: psycopg.Connection,
    *,
    id: str,
    name: str,
    kind: str,
    roundtrip: bool,
    osm_relation_id: int | None,
    length_km: float,
    ascent_m: int,
    descent_m: int,
    profile: list[tuple[float, float]],
    line: Sequence[tuple[float, float]],
    source_id: str,
) -> None:
    conn.execute(
        """
        insert into trails (id, name, kind, roundtrip, osm_relation_id, length_km, ascent_m,
                            descent_m, profile, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s, %(roundtrip)s, %(rel)s, %(len)s, %(asc)s, %(desc)s,
                %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind, roundtrip = excluded.roundtrip,
            osm_relation_id = excluded.osm_relation_id, length_km = excluded.length_km,
            ascent_m = excluded.ascent_m, descent_m = excluded.descent_m,
            profile = excluded.profile, geom = excluded.geom, source_id = excluded.source_id
        """,
        {
            "id": id,
            "name": name,
            "kind": kind,
            "roundtrip": roundtrip,
            "rel": osm_relation_id,
            "len": length_km,
            "asc": ascent_m,
            "desc": descent_m,
            "profile": Jsonb(profile),
            "wkt": _wkt(line),
            "src": source_id,
        },
    )


def upsert_stage(
    conn: psycopg.Connection,
    *,
    id: str,
    trail_id: str,
    seq: int,
    name: str,
    start_name: str,
    end_name: str,
    length_km: float,
    ascent_m: int,
    descent_m: int,
    profile: list[tuple[float, float]],
    line: Sequence[tuple[float, float]],
    source_id: str,
) -> None:
    conn.execute(
        """
        insert into stages (id, trail_id, seq, name, start_name, end_name, length_km,
                            ascent_m, descent_m, profile, geom, source_id)
        values (%(id)s, %(trail)s, %(seq)s, %(name)s, %(start)s, %(end)s, %(len)s, %(asc)s,
                %(desc)s, %(profile)s, st_geomfromtext(%(wkt)s, 4326), %(src)s)
        on conflict (id) do update set
            trail_id = excluded.trail_id, seq = excluded.seq, name = excluded.name,
            start_name = excluded.start_name, end_name = excluded.end_name,
            length_km = excluded.length_km, ascent_m = excluded.ascent_m,
            descent_m = excluded.descent_m, profile = excluded.profile, geom = excluded.geom,
            source_id = excluded.source_id
        """,
        {
            "id": id,
            "trail": trail_id,
            "seq": seq,
            "name": name,
            "start": start_name,
            "end": end_name,
            "len": length_km,
            "asc": ascent_m,
            "desc": descent_m,
            "profile": Jsonb(profile),
            "wkt": _wkt(line),
            "src": source_id,
        },
    )


def delete_stages_after(conn: psycopg.Connection, trail_id: str, last_seq: int) -> None:
    """Remove stages beyond `last_seq`, so a shortened stage list leaves nothing behind."""
    conn.execute("delete from stages where trail_id = %s and seq > %s", [trail_id, last_seq])


def delete_day_hike(conn: psycopg.Connection, trail_id: str) -> bool:
    """Remove a day hike and its lodging links; True if a trail was deleted.

    Long-distance trails (with stages) are never touched here."""
    conn.execute(
        "delete from trail_lodgings where trail_id = %s"
        " and exists (select 1 from trails where id = %s and kind = 'day_hike')",
        [trail_id, trail_id],
    )
    cur = conn.execute("delete from trails where id = %s and kind = 'day_hike'", [trail_id])
    return cur.rowcount > 0


def upsert_lodging(conn: psycopg.Connection, lodging: Lodging, source_id: str) -> None:
    conn.execute(
        """
        insert into lodgings (id, name, kind, website, geom, source_id)
        values (%(id)s, %(name)s, %(kind)s, %(website)s,
                st_setsrid(st_makepoint(%(lon)s, %(lat)s), 4326), %(src)s)
        on conflict (id) do update set
            name = excluded.name, kind = excluded.kind, website = excluded.website,
            geom = excluded.geom, source_id = excluded.source_id
        """,
        {**lodging.model_dump(), "src": source_id},
    )
